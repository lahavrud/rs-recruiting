"""Async task definitions and SQS producer.

Tasks are plain async functions — no Arq context arg. They are called
directly by the SQS worker (src/worker.py) and inline during local dev
(when SQS_QUEUE_URL is not configured).

Public API (unchanged from Arq era — all 10+ call sites still work):
  enqueue_email_task(to, subject, body, ...)  → MessageId | "inline"
  enqueue_data_export_task(user_id)           → MessageId | "inline"
"""

import base64
import json
import logging
import time
from typing import List, Optional

import aioboto3
from opentelemetry import metrics as otel_metrics

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import async_session
from src.core.infrastructure.transactions import transactional
from src.core.matching import embed_job_task, match_candidate_task
from src.core.services.email import get_email_provider
from src.core.services.email_quota import increment_and_alert
from src.core.utils import mask_email

logger = logging.getLogger(__name__)

_meter = otel_metrics.get_meter("src.core.tasks")
_purged_counter = _meter.create_counter(
    name="purged_candidates",
    description="Number of candidate records purged by the retention task",
    unit="1",
)
_last_purge_ran_gauge = _meter.create_gauge(
    name="last_purge_ran_at",
    description="Unix timestamp of the last successful retention purge run",
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
    so SQS redelivery is safe.
    """
    from src.core.services.storage import get_storage_provider
    from src.services.candidate.data_export import (
        DATA_EXPORT_TTL_HOURS,
        build_and_persist_export,
        has_pending_export,
    )
    from src.templates.email import build_data_export_ready_html

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
        logger.exception("Failed to enqueue data export notification email")


async def purge_expired_candidate_data_task() -> int:
    """Purge candidates past the 12-month retention window.

    Triggered nightly by EventBridge Scheduler → SQS.
    """
    from src.services.admin.candidates import purge_expired_candidates

    async with async_session() as session:
        async with transactional(session):
            count = await purge_expired_candidates(session)
    attrs = {"environment": settings.environment}
    _purged_counter.add(count, attrs)
    _last_purge_ran_gauge.set(time.time(), attrs)
    logger.info("purge_complete", extra={"count": count})
    return count


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

    serialized_attachments = None
    if attachments:
        serialized_attachments = [
            [name, base64.b64encode(data).decode(), mime]
            for name, data, mime in attachments
        ]

    message_id = await _sqs_send(
        {
            "task": "send_email",
            "to": to,
            "subject": subject,
            "body": body,
            "html_body": html_body,
            "attachments": serialized_attachments,
            "from_email": from_email,
        }
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

    message_id = await _sqs_send({"task": "build_data_export", "user_id": user_id})
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

    message_id = await _sqs_send({"task": "embed_job", "job_id": job_id})
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

    message_id = await _sqs_send(
        {"task": "match_candidate", "candidate_id": candidate_id}
    )
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
    "send_email": send_email_task,
    "build_data_export": build_data_export_task,
    "purge_expired_candidates": purge_expired_candidate_data_task,
    "embed_job": embed_job_task,
    "match_candidate": match_candidate_task,
}
