"""Outbox row lifecycle — the DB half of transactional email delivery.

Framework-free and SQS-free on purpose: this module only moves ``EmailOutbox``
rows between states. The producer/consumer wiring (inserting inside the
caller's transaction, nudging SQS, calling the provider) lives in
``core/tasks.py``, which imports from here. Keeping the dependency one-way
avoids a cycle and keeps the state machine testable without a queue.

State machine (see ``enums.EmailStatus``)::

    PENDING ──claim_for_send──► SENDING ──mark_sent───────► SENT
                                        ├─mark_for_retry──► PENDING
                                        └─mark_failed─────► FAILED

``claim_for_send`` is the idempotency guard. SQS is at-least-once, so the same
``outbox_id`` can arrive more than once; only a row in PENDING is claimable,
which makes a redelivered send a no-op instead of a second email.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.services.email_quota import increment_and_alert
from rs_shared.core.task_contract import Attachment, encode_attachments
from rs_shared.enums import EmailStatus
from rs_shared.models import EmailOutbox

logger = logging.getLogger(__name__)

# After this many attempts a row is parked in FAILED rather than redelivered
# forever. SQS's maxReceiveCount would eventually DLQ it anyway; parking it
# here keeps the reason queryable next to the payload.
MAX_SEND_ATTEMPTS = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def insert_email(
    session: AsyncSession,
    to: str | list[str],
    subject: str,
    body: str,
    html_body: str | None = None,
    attachments: list[Attachment] | None = None,
    from_email: str | None = None,
    dedup_key: str | None = None,
) -> int | None:
    """Insert a PENDING outbox row in the caller's transaction.

    Returns the new row id, or ``None`` when ``dedup_key`` collided with an
    existing row (the email is already queued or sent — nothing to do).

    Uses ``ON CONFLICT DO NOTHING`` rather than catching IntegrityError: a
    constraint violation would poison the caller's transaction and roll back
    the domain change that triggered the email. A NULL ``dedup_key`` never
    conflicts (Postgres treats NULLs as distinct), so opting out is the
    default.
    """
    now = _now()
    stmt = (
        pg_insert(EmailOutbox.__table__)
        .values(
            dedup_key=dedup_key,
            to_addrs=[to] if isinstance(to, str) else list(to),
            subject=subject,
            body=body,
            html_body=html_body,
            attachments=encode_attachments(attachments),
            from_email=from_email,
            status=EmailStatus.PENDING.value,
            attempts=0,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["dedup_key"])
        .returning(EmailOutbox.__table__.c.id)
    )
    outbox_id = (await session.execute(stmt)).scalar_one_or_none()
    if outbox_id is None:
        logger.info("email_deduped", extra={"dedup_key": dedup_key})
    return outbox_id


async def claim_for_send(session: AsyncSession, outbox_id: int) -> EmailOutbox | None:
    """Lock a row and transition PENDING → SENDING.

    Returns the row when the caller now owns the send, or ``None`` when it
    must not send. ``None`` covers every not-our-turn case:

    * SENT / FAILED — terminal; a redelivered message lands here and no-ops.
    * SENDING — a previous attempt reached this point and did not finish. It
      may or may not have hit the provider, so resending risks a duplicate.
      We refuse and let ``sweep_email_outbox_task`` surface it for a human.
      That trades a possible lost email for never double-emailing a candidate.
    """
    row = (
        await session.execute(
            select(EmailOutbox).where(EmailOutbox.id == outbox_id).with_for_update()
        )
    ).scalar_one_or_none()

    if row is None:
        logger.warning("outbox_row_missing", extra={"outbox_id": outbox_id})
        return None
    if row.status in (EmailStatus.SENT, EmailStatus.FAILED):
        logger.info(
            "outbox_send_skipped_terminal",
            extra={"outbox_id": outbox_id, "status": row.status},
        )
        return None
    if row.status == EmailStatus.SENDING:
        logger.critical(
            "outbox_row_stuck_sending",
            extra={"outbox_id": outbox_id, "attempts": row.attempts},
        )
        return None

    row.status = EmailStatus.SENDING
    row.attempts += 1
    row.updated_at = _now()
    return row


async def mark_sent(
    session: AsyncSession, row: EmailOutbox, provider_message_id: str | None
) -> None:
    """Record a successful send and bump the quota — in one transaction.

    The quota increment belongs here, not in a separate transaction after the
    send: when it lived on its own, a failed quota write raised, SQS
    redelivered, and the recipient got the email twice. Sharing this
    transaction means a failure leaves the row in SENDING, which
    ``claim_for_send`` refuses to resend — an under-counted quota (advisory,
    never enforced) instead of a duplicate email.
    """
    row.status = EmailStatus.SENT
    row.sent_at = _now()
    row.updated_at = row.sent_at
    row.provider_message_id = provider_message_id
    row.last_error = None
    await increment_and_alert(session)


async def mark_for_retry(session: AsyncSession, row: EmailOutbox, error: str) -> None:
    """Return a row to PENDING so an SQS redelivery can claim it again."""
    row.status = EmailStatus.PENDING
    row.last_error = error[:2000]
    row.updated_at = _now()


async def mark_failed(session: AsyncSession, row: EmailOutbox, error: str) -> None:
    """Park a row in FAILED — out of attempts, no further redelivery."""
    row.status = EmailStatus.FAILED
    row.last_error = error[:2000]
    row.updated_at = _now()
    logger.critical(
        "outbox_send_failed_permanently",
        extra={"outbox_id": row.id, "attempts": row.attempts},
    )


async def stale_pending_ids(
    session: AsyncSession, older_than: datetime, limit: int = 100
) -> list[int]:
    """PENDING rows whose SQS nudge never landed — the sweeper's work list."""
    result = await session.execute(
        select(EmailOutbox.id)
        .where(
            EmailOutbox.status == EmailStatus.PENDING,
            EmailOutbox.created_at < older_than,
        )
        .order_by(EmailOutbox.created_at)
        .limit(limit)
    )
    return list(result.scalars().all())


async def stale_sending_ids(
    session: AsyncSession, older_than: datetime, limit: int = 100
) -> list[int]:
    """SENDING rows that never resolved — ambiguous, needs a human."""
    result = await session.execute(
        select(EmailOutbox.id)
        .where(
            EmailOutbox.status == EmailStatus.SENDING,
            EmailOutbox.updated_at < older_than,
        )
        .order_by(EmailOutbox.updated_at)
        .limit(limit)
    )
    return list(result.scalars().all())
