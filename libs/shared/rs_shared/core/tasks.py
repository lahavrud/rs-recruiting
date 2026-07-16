"""Async task definitions and SQS producer.

Tasks are plain async functions — no Arq context arg. They are called
directly by the SQS worker (rs_worker/worker.py) and inline during local dev
(when SQS_QUEUE_URL is not configured).

The wire format of every message (the ``{"task": ..., ...kwargs}`` envelope and
its attachment encoding) is defined once in ``rs_shared.core.task_contract`` and
shared with the worker so the two sides cannot drift.

Public API (unchanged from Arq era — all 10+ call sites still work):
  enqueue_email_task(to, subject, body, ...)  → MessageId | "inline"
  enqueue_data_export_task(user_id)           → MessageId | "inline"
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import aioboto3
from opentelemetry import metrics as otel_metrics
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.infrastructure.database import async_session
from rs_shared.core.infrastructure.transactions import (
    defer_after_commit,
    transactional,
)
from rs_shared.core.matching import embed_job_task, match_candidate_task
from rs_shared.core.services import email_outbox
from rs_shared.core.services.email import get_email_provider
from rs_shared.core.services.email_quota import increment_and_alert
from rs_shared.core.task_contract import (
    Attachment,
    TaskName,
    build_data_export_message,
    build_email_message,
    build_embed_job_message,
    build_match_candidate_message,
    build_send_outbox_email_message,
    decode_attachments,
)
from rs_shared.core.utils import mask_email
from rs_shared.models import EmailOutbox

logger = logging.getLogger(__name__)

_meter = otel_metrics.get_meter("rs_shared.core.tasks")
_purged_counter = _meter.create_counter(
    name="purged_candidates",
    description="Number of candidate records purged by the retention task",
    unit="1",
)
_unactivated_users_counter = _meter.create_counter(
    name="purged_unactivated_users",
    description="Unactivated CANDIDATE users deleted by the nightly cleanup",
    unit="1",
)
_export_zips_counter = _meter.create_counter(
    name="purged_export_zips",
    description="Expired DataExportRequest rows deleted by the nightly cleanup",
    unit="1",
)
_deletion_tokens_counter = _meter.create_counter(
    name="purged_deletion_tokens",
    description="Expired/used AccountDeletionToken rows deleted by the nightly cleanup",
    unit="1",
)
_activation_tokens_counter = _meter.create_counter(
    name="purged_activation_tokens",
    description="Stale ActivationToken rows deleted by the nightly cleanup",
    unit="1",
)
_last_purge_ran_gauge = _meter.create_gauge(
    name="last_purge_ran_at",
    description="Unix timestamp of the last successful nightly cleanup run",
    unit="s",
)


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
                await email_outbox.mark_sent(
                    session, row, _provider_message_id(success)
                )
    logger.info(
        "email_sent", extra={"outbox_id": outbox_id, "to": mask_email(to_addrs)}
    )
    return True


def _provider_message_id(send_result: bool | str) -> str | None:
    """Providers return bool today; tolerate a message-id when they don't.

    ``EmailProvider.send_email`` is typed ``-> bool``, so there is no id to
    record yet. Returning the id is part of the typed-provider follow-up; this
    keeps the column wired so that change is a one-liner.
    """
    return send_result if isinstance(send_result, str) else None


async def sweep_email_outbox_task() -> dict:
    """Backstop for rows that never got sent.

    Two failure modes, two treatments:

    * PENDING past the threshold — the post-commit SQS nudge never landed
      (the exact silent-loss path this outbox exists to close). Re-enqueue.
    * SENDING past the threshold — a worker claimed it and never resolved.
      Ambiguous: it may already be in the recipient's inbox. Logged CRITICAL
      for a human rather than resent.

    Scheduled by EventBridge → SQS, which lives in the infra repo. Until that
    rule exists this is still runnable as a one-off ECS task.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.email_outbox_sweep_after_minutes
    )
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


async def build_data_export_task(user_id: int) -> None:
    """Assemble a candidate GDPR export ZIP and email the download link.

    Idempotent guard: if a pending export already exists the task is a no-op
    so SQS redelivery is safe.
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


async def nightly_cleanup_task() -> dict:
    """Nightly data-hygiene dispatcher.

    Runs five independent sub-tasks in sequence; a failure in one does not
    abort the rest. Each sub-task is wrapped in its own transaction.

    Triggered nightly by EventBridge Scheduler → SQS (message task key:
    ``purge_expired_candidates`` — unchanged from the previous single-task
    registration for backward compatibility with the existing EventBridge rule).

    Returns a summary dict of counts per sub-task.
    """
    from rs_shared.services.admin._candidates_purge import purge_expired_candidates
    from rs_shared.services.admin.maintenance import (
        purge_expired_account_deletion_tokens,
        purge_expired_activation_tokens,
        purge_expired_data_export_zips,
        purge_unactivated_candidate_users,
    )

    results: dict[str, int | None] = {}

    async def _run(name: str, coro) -> int | None:
        try:
            async with async_session() as session:
                async with transactional(session):
                    return await coro(session)
        except Exception:
            logger.exception("nightly_cleanup_subtask_failed", extra={"subtask": name})
            return None

    results["purge_expired_candidates"] = await _run(
        "purge_expired_candidates", purge_expired_candidates
    )
    results["purge_unactivated_users"] = await _run(
        "purge_unactivated_users", purge_unactivated_candidate_users
    )
    results["purge_export_zips"] = await _run(
        "purge_export_zips", purge_expired_data_export_zips
    )
    results["purge_deletion_tokens"] = await _run(
        "purge_deletion_tokens", purge_expired_account_deletion_tokens
    )
    results["purge_activation_tokens"] = await _run(
        "purge_activation_tokens", purge_expired_activation_tokens
    )

    attrs_env = {"environment": settings.environment}
    _purged_counter.add(results["purge_expired_candidates"] or 0, attrs_env)
    _unactivated_users_counter.add(results["purge_unactivated_users"] or 0, attrs_env)
    _export_zips_counter.add(results["purge_export_zips"] or 0, attrs_env)
    _deletion_tokens_counter.add(results["purge_deletion_tokens"] or 0, attrs_env)
    _activation_tokens_counter.add(results["purge_activation_tokens"] or 0, attrs_env)
    if any(v is not None for v in results.values()):
        _last_purge_ran_gauge.set(time.time(), attrs_env)

    logger.info("nightly_cleanup_complete", extra=results)
    return results


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
}
