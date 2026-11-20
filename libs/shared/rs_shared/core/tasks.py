"""Async task definitions and SQS producer.

Tasks are plain async functions — no Arq context arg. They are called
directly by the SQS worker (rs_worker/worker.py) and inline during local dev
(when SQS_QUEUE_URL is not configured).

The wire format of every message (the ``{"task": ..., ...kwargs}`` envelope and
its attachment encoding) is defined once in ``rs_shared.core.task_contract`` and
shared with the worker so the two sides cannot drift.

Public API:
  queue_email(session, to, subject, body, ...)  → outbox_id | None (deduped)
  enqueue_data_export_task(user_id)             → MessageId | "inline"

``queue_email`` is the producer for email: it writes an ``email_outbox`` row in
the caller's transaction and defers only the SQS nudge, so a committed domain
change can never be left without its email. It must be called from inside a
``transactional()`` block. ``enqueue_email_task`` / ``send_email_task`` are the
legacy pre-outbox path, retained for one release to drain in-flight
``send_email`` messages — do not call them from new code.
"""

import json
import logging
from typing import List, Optional

import aioboto3
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.email_tasks import send_email_task, send_outbox_email_task
from rs_shared.core.infrastructure.config import settings
from rs_shared.core.infrastructure.database import async_session
from rs_shared.core.infrastructure.transactions import (
    defer_after_commit,
    transactional,
)
from rs_shared.core.matching import embed_job_task, match_candidate_task
from rs_shared.core.scheduled_tasks import (
    nightly_cleanup_task,
    send_admin_digest_task,
)
from rs_shared.core.services import email_outbox
from rs_shared.core.task_contract import (
    Attachment,
    TaskName,
    build_data_export_message,
    build_email_message,
    build_embed_job_message,
    build_match_candidate_message,
    build_send_outbox_email_message,
)
from rs_shared.core.utils import mask_email

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _sqs_send(message: dict) -> str:
    """Serialize and send one message to the configured SQS queue."""
    session = aioboto3.Session()
    async with session.client(
        "sqs",
        region_name=settings.aws_region,
        endpoint_url=settings.sqs_endpoint_url,
    ) as sqs:
        resp = await sqs.send_message(
            QueueUrl=settings.sqs_queue_url,
            MessageBody=json.dumps(message),
        )
    return resp["MessageId"]


# ---------------------------------------------------------------------------
# Task implementations (called by the worker — no Arq ctx arg)
# ---------------------------------------------------------------------------


async def sweep_email_outbox_task() -> dict:
    """Backstop for rows that never got sent.

    Two failure modes, two treatments:

    * PENDING past the threshold — the post-commit SQS nudge never landed
      (the exact silent-loss path this outbox exists to close). Re-enqueue.
    * SENDING past the threshold — a worker claimed it and never resolved.
      Ambiguous: it may already be in the recipient's inbox. Logged CRITICAL
      for a human rather than resent.

    Scheduled every 5 minutes by EventBridge → SQS (``outbox_sweep`` in the
    infra repo's ``tofu/modules/sqs/main.tf``).
    """
    cutoff = email_outbox.sweep_cutoff()
    async with async_session() as session:
        pending = await email_outbox.stale_pending_ids(session, cutoff)
        stuck = await email_outbox.stale_sending_ids(session, cutoff)

    for outbox_id in pending:
        await enqueue_send_outbox_email_task(outbox_id)

    if stuck:
        logger.critical("outbox_rows_stuck_sending", extra={"outbox_ids": stuck})

    result = {"requeued": len(pending), "stuck_sending": len(stuck)}
    logger.info("outbox_sweep_complete", extra=result)
    return result


async def build_data_export_task(user_id: int) -> None:
    """Assemble a candidate GDPR export ZIP and email the download link.

    Idempotent guard: if a pending export already exists the task is a no-op
    so SQS redelivery is safe. The export row and the email that carries its
    download link commit together, so that guard can never outlive the link.
    """
    from rs_shared.core.services.storage import get_storage_provider
    from rs_shared.services.candidate.data_export import (
        DATA_EXPORT_TTL_HOURS,
        build_and_persist_export,
        has_pending_export,
    )
    from rs_shared.templates.email import build_data_export_ready_html

    # Idempotency guard — SQS is at-least-once
    async with async_session() as session:
        if await has_pending_export(user_id, session):
            logger.info(
                "data_export_skipped_pending_exists", extra={"user_id": user_id}
            )
            return

    # The export row and the email announcing it commit together — the ZIP is
    # useless to the candidate if the link never reaches them, and this used to
    # enqueue afterwards behind a try/except that swallowed the failure.
    async with async_session() as session:
        async with transactional(session):
            raw_token, candidate_email = await build_and_persist_export(
                user_id, session, get_storage_provider()
            )
            download_url = (
                f"{settings.frontend_base_url}/api/candidate/me/export/{raw_token}"
            )
            await queue_email(
                session,
                to=candidate_email,
                subject="ייצוא הנתונים שלכם מוכן – RS Recruiting",
                body=(
                    "שלום,\n\n"
                    "ייצוא הנתונים שביקשתם מוכן להורדה.\n\n"
                    f"קישור להורדה (תקף ל-{DATA_EXPORT_TTL_HOURS} שעות):\n"
                    f"{download_url}\n\n"
                    "בברכה,\nצוות RS Recruiting"
                ),
                html_body=build_data_export_ready_html(
                    download_url=download_url, ttl_hours=DATA_EXPORT_TTL_HOURS
                ),
            )


# ---------------------------------------------------------------------------
# Producer — enqueue into SQS (or run inline when SQS_QUEUE_URL is not set)
# ---------------------------------------------------------------------------


async def queue_email(
    session: AsyncSession,
    to: str | List[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[Attachment]] = None,
    from_email: Optional[str] = None,
    dedup_key: Optional[str] = None,
) -> Optional[int]:
    """Queue an email as part of the caller's transaction. The producer API.

    Call this *inside* a ``transactional()`` block, from the service that owns
    the domain change. The outbox row is written in that same transaction, so
    committing the change and queueing its email are one atomic act: an
    approved company can no longer end up without its activation email.

    The SQS nudge is deferred to after the commit — it must not fire for a
    transaction that rolls back. If the nudge fails, the committed PENDING row
    is still there and ``sweep_email_outbox_task`` re-enqueues it; that is the
    difference from the old ``defer_after_commit(enqueue_email_task)``, where a
    failed enqueue meant the email was simply never sent.

    ``dedup_key`` is optional business-level idempotency: pass a deterministic
    key for the domain event (``f"password_reset:{token.id}"``) and a second
    queue of the same event is dropped. Returns the outbox row id, or None when
    the email was deduped.
    """
    outbox_id = await email_outbox.insert_email(
        session,
        to=to,
        subject=subject,
        body=body,
        html_body=html_body,
        attachments=attachments,
        from_email=from_email,
        dedup_key=dedup_key,
    )
    if outbox_id is None:
        return None

    defer_after_commit(lambda: enqueue_send_outbox_email_task(outbox_id))
    return outbox_id


async def enqueue_send_outbox_email_task(outbox_id: int) -> str:
    """Nudge the worker to send an already-committed outbox row.

    Runs the send inline when SQS_QUEUE_URL is unset (local dev), matching the
    other producers. Note the nudge carries only the id — see
    ``build_send_outbox_email_message``.
    """
    if not settings.sqs_queue_url:
        await send_outbox_email_task(outbox_id)
        return "inline"

    message_id = await _sqs_send(build_send_outbox_email_message(outbox_id))
    logger.info(
        "email_enqueued", extra={"message_id": message_id, "outbox_id": outbox_id}
    )
    return message_id


async def enqueue_email_task(
    to: str | List[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[tuple]] = None,
    from_email: Optional[str] = None,
) -> str:
    """Legacy producer — enqueues the payload on the wire, with no outbox row.

    Superseded by ``queue_email``. Retained only because it has no session to
    write a row with; any remaining caller gets the old at-least-once, no-record
    behaviour. Prefer ``queue_email`` for anything transactional.
    """
    if not settings.sqs_queue_url:
        await send_email_task(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            attachments=attachments,
            from_email=from_email,
        )
        return "inline"

    message_id = await _sqs_send(
        build_email_message(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            attachments=attachments,
            from_email=from_email,
        )
    )
    logger.info(
        "email_enqueued", extra={"message_id": message_id, "to": mask_email(to)}
    )
    return message_id


async def enqueue_data_export_task(user_id: int) -> str:
    """Enqueue the GDPR data export build for a candidate.

    When SQS_QUEUE_URL is not configured the task is spawned as a
    background asyncio task (local dev — avoids blocking the request).
    """
    if not settings.sqs_queue_url:
        import asyncio

        asyncio.create_task(build_data_export_task(user_id))
        return "inline"

    message_id = await _sqs_send(build_data_export_message(user_id))
    logger.info(
        "data_export_enqueued", extra={"message_id": message_id, "user_id": user_id}
    )
    return message_id


async def enqueue_embed_job_task(job_id: int) -> str:
    """Enqueue a job re-embed. Runs inline (background task) in local dev."""
    if not settings.sqs_queue_url:
        import asyncio

        asyncio.create_task(embed_job_task(job_id))
        return "inline"

    message_id = await _sqs_send(build_embed_job_message(job_id))
    logger.info(
        "embed_job_enqueued", extra={"message_id": message_id, "job_id": job_id}
    )
    return message_id


async def enqueue_match_candidate_task(candidate_id: int) -> str:
    """Enqueue a candidate re-match. Runs inline (background task) in local dev."""
    if not settings.sqs_queue_url:
        import asyncio

        asyncio.create_task(match_candidate_task(candidate_id))
        return "inline"

    message_id = await _sqs_send(build_match_candidate_message(candidate_id))
    logger.info(
        "match_candidate_enqueued",
        extra={"message_id": message_id, "candidate_id": candidate_id},
    )
    return message_id


# ---------------------------------------------------------------------------
# Task registry — used by the worker to dispatch received SQS messages
# ---------------------------------------------------------------------------

# Maps the "task" field in the SQS message body to the implementing coroutine.
# Add new tasks here; the worker picks them up without any other changes.
TASK_REGISTRY: dict = {
    TaskName.SEND_OUTBOX_EMAIL: send_outbox_email_task,
    TaskName.SWEEP_EMAIL_OUTBOX: sweep_email_outbox_task,
    # Legacy — drains send_email messages still in flight from the previous
    # release. Nothing produces these any more; remove next release.
    TaskName.SEND_EMAIL: send_email_task,
    TaskName.BUILD_DATA_EXPORT: build_data_export_task,
    # Wire-format key kept as PURGE_EXPIRED_CANDIDATES for backward compatibility
    # with the existing EventBridge Scheduler rule. Update the rule to send
    # "nightly_cleanup" after this deploys.
    TaskName.PURGE_EXPIRED_CANDIDATES: nightly_cleanup_task,
    TaskName.EMBED_JOB: embed_job_task,
    TaskName.MATCH_CANDIDATE: match_candidate_task,
    TaskName.SEND_ADMIN_DIGEST: send_admin_digest_task,
}
