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
from typing import List, Optional

import aioboto3
from opentelemetry import metrics as otel_metrics

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.infrastructure.database import async_session
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.core.matching import embed_job_task, match_candidate_task
from rs_shared.core.services.email import get_email_provider
from rs_shared.core.services.email_quota import increment_and_alert
from rs_shared.core.task_contract import (
    TaskName,
    build_data_export_message,
    build_email_message,
    build_embed_job_message,
    build_match_candidate_message,
)
from rs_shared.core.utils import mask_email

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


async def send_email_task(
    to: str | List[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[tuple]] = None,
    from_email: Optional[str] = None,
) -> bool:
    """Send an email via the configured provider. Called by the SQS worker."""
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
    so SQS redelivery is safe. That guard is also why a failed notification
    has to discard the export it just built — see the except below.
    """
    from rs_shared.core.services.storage import get_storage_provider
    from rs_shared.services.candidate.data_export import (
        DATA_EXPORT_TTL_HOURS,
        build_and_persist_export,
        discard_export,
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

    async with async_session() as session:
        async with transactional(session):
            raw_token, candidate_email = await build_and_persist_export(
                user_id, session, get_storage_provider()
            )

    download_url = f"{settings.frontend_base_url}/api/candidate/me/export/{raw_token}"
    html = build_data_export_ready_html(
        download_url=download_url, ttl_hours=DATA_EXPORT_TTL_HOURS
    )
    try:
        await enqueue_email_task(
            to=candidate_email,
            subject="ייצוא הנתונים שלכם מוכן – RS Recruiting",
            body=(
                "שלום,\n\n"
                "ייצוא הנתונים שביקשתם מוכן להורדה.\n\n"
                f"קישור להורדה (תקף ל-{DATA_EXPORT_TTL_HOURS} שעות):\n"
                f"{download_url}\n\n"
                "בברכה,\nצוות RS Recruiting"
            ),
            html_body=html,
        )
    except Exception:
        # The export row is the idempotency guard above *and* the API's 429
        # rate limit. Acking here would strand the candidate: the ZIP exists,
        # the link never arrives, redelivery no-ops on the guard, and they get
        # a 429 for the full TTL. Expire the export so redelivery rebuilds,
        # then let the failure propagate to the worker (and eventually the DLQ).
        try:
            async with async_session() as session:
                async with transactional(session):
                    await discard_export(raw_token, session)
        except Exception:
            logger.exception("data_export_discard_failed", extra={"user_id": user_id})
        raise


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


async def enqueue_email_task(
    to: str | List[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[tuple]] = None,
    from_email: Optional[str] = None,
) -> str:
    """Enqueue an email send. Call sites are unchanged from the Arq era.

    Attachments (bytes) are base64-encoded for JSON transport over SQS.
    Single-page PDFs are ~20–80 KB — well under the 256 KB SQS message limit.

    When SQS_QUEUE_URL is not configured the task runs inline (local dev).
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
    TaskName.SEND_EMAIL: send_email_task,
    TaskName.BUILD_DATA_EXPORT: build_data_export_task,
    # Wire-format key kept as PURGE_EXPIRED_CANDIDATES for backward compatibility
    # with the existing EventBridge Scheduler rule. Update the rule to send
    # "nightly_cleanup" after this deploys.
    TaskName.PURGE_EXPIRED_CANDIDATES: nightly_cleanup_task,
    TaskName.EMBED_JOB: embed_job_task,
    TaskName.MATCH_CANDIDATE: match_candidate_task,
}
