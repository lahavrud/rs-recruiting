"""Email-sending task implementations (consumer side).

``send_outbox_email_task`` delivers one ``email_outbox`` row; ``send_email_task``
is the legacy direct-send consumer kept to drain in-flight messages (see
CLAUDE.md). Producers (``queue_email``, ``enqueue_*``) and the sweeper stay in
``tasks.py``. Split out of it to keep it under the 300-line cap.
"""

import logging
from typing import List, Optional

from rs_shared.core.infrastructure.database import async_session
from rs_shared.core.infrastructure.transactions import (
    transactional,
)
from rs_shared.core.services import email_outbox
from rs_shared.core.services.email import get_email_provider
from rs_shared.core.services.email_quota import increment_and_alert
from rs_shared.core.task_contract import (
    decode_attachments,
)
from rs_shared.core.utils import mask_email
from rs_shared.models import EmailOutbox

logger = logging.getLogger(__name__)


async def send_outbox_email_task(outbox_id: int) -> bool:
    """Send one outbox row. The worker's entry point for email.

    Three transactions, deliberately:

    1. Claim the row (PENDING → SENDING) and commit, so a concurrent
       redelivery can't claim it too.
    2. Call the provider — outside any transaction, so a slow SMTP/SES round
       trip never holds a row lock or a pooled connection.
    3. Record the outcome. On success the quota bump shares this transaction
       (see ``email_outbox.mark_sent`` for why).

    Returns True when this call sent the email; False when there was nothing
    to do (already sent, terminal, or claimed by someone else) — both mean the
    SQS message should be deleted. Transient failures raise so SQS redelivers.
    """
    async with async_session() as session:
        async with transactional(session):
            row = await email_outbox.claim_for_send(session, outbox_id)
            if row is None:
                return False
            # Snapshot what the send needs; the row is detached after commit.
            to_addrs = list(row.to_addrs)
            subject = row.subject
            body = row.body
            html_body = row.html_body
            attachments = decode_attachments(row.attachments)
            from_email = row.from_email
            attempts = row.attempts

    logger.info(
        "sending_email",
        extra={"outbox_id": outbox_id, "to": mask_email(to_addrs), "subject": subject},
    )
    try:
        provider = get_email_provider()
        success = await provider.send_email(
            to=to_addrs,
            subject=subject,
            body=body,
            html_body=html_body,
            attachments=attachments,
            from_email=from_email,
        )
        if not success:
            raise RuntimeError(f"Email provider returned False for outbox {outbox_id}")
    except Exception as exc:
        # The provider collapses every error into False/an exception, so we
        # can't yet tell "invalid address" (permanent) from "SES throttled"
        # (transient) — everything is retried until MAX_SEND_ATTEMPTS. Typed
        # provider errors are the follow-up that makes this distinction.
        async with async_session() as session:
            async with transactional(session):
                row = await session.get(EmailOutbox, outbox_id)
                if row is None:
                    raise
                if attempts >= email_outbox.MAX_SEND_ATTEMPTS:
                    await email_outbox.mark_failed(session, row, str(exc))
                    return False
                await email_outbox.mark_for_retry(session, row, str(exc))
        logger.error(
            "email_error",
            extra={"outbox_id": outbox_id, "to": mask_email(to_addrs)},
            exc_info=True,
        )
        raise

    async with async_session() as session:
        async with transactional(session):
            row = await session.get(EmailOutbox, outbox_id)
            if row is not None:
                # provider_message_id stays NULL until EmailProvider.send_email
                # returns the provider's id instead of a bool — it is typed
                # `-> bool`, so there is nothing to record yet.
                await email_outbox.mark_sent(session, row, None)
    logger.info(
        "email_sent", extra={"outbox_id": outbox_id, "to": mask_email(to_addrs)}
    )
    return True


async def send_email_task(
    to: str | List[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[tuple]] = None,
    from_email: Optional[str] = None,
) -> bool:
    """Legacy send path — payload carried on the wire, no outbox row.

    Superseded by ``send_outbox_email_task``. Kept only to drain ``send_email``
    messages already in flight during the rolling deploy (rules/worker.md:
    message-format changes must be consumed-side backward-compatible). Delete
    once the queue has drained; nothing enqueues this any more.
    """
    logger.info("sending_email", extra={"to": mask_email(to), "subject": subject})
    try:
        provider = get_email_provider()
        success = await provider.send_email(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            attachments=attachments,
            from_email=from_email,
        )
        if success:
            logger.info("email_sent", extra={"to": mask_email(to)})
            async with async_session() as session:
                async with transactional(session):
                    await increment_and_alert(session)
        else:
            logger.warning("email_send_failed", extra={"to": mask_email(to)})
            raise RuntimeError(f"Email provider returned False for {mask_email(to)}")
        return success
    except Exception as e:
        logger.error(
            "email_error", extra={"to": mask_email(to), "error": str(e)}, exc_info=True
        )
        raise
