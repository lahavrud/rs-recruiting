"""Scheduled task implementations: the nightly cleanup and the admin digest.

Both are triggered by EventBridge Scheduler -> SQS (schedules live in
rs-recruiting-infra) and dispatched through ``TASK_REGISTRY`` in ``tasks.py``.
Split out of ``tasks.py`` to keep it under the 300-line cap.
"""

import logging
import time

from opentelemetry import metrics as otel_metrics

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.infrastructure.database import async_session
from rs_shared.core.infrastructure.transactions import (
    transactional,
)

logger = logging.getLogger(__name__)

# Keep the meter name: these counters were created on "rs_shared.core.tasks"
# before the split, and dashboards may filter on that instrumentation scope.
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
_outbox_redacted_counter = _meter.create_counter(
    name="redacted_email_outbox",
    description="Terminal email_outbox rows whose content the nightly cleanup cleared",
    unit="1",
)
_outbox_purged_counter = _meter.create_counter(
    name="purged_email_outbox",
    description="Terminal email_outbox rows deleted by the nightly cleanup",
    unit="1",
)
_login_throttle_purged_counter = _meter.create_counter(
    name="purged_login_throttle",
    description="Stale login_throttle rows deleted by the nightly cleanup",
    unit="1",
)
_mfa_challenges_purged_counter = _meter.create_counter(
    name="purged_mfa_challenges",
    description="Expired MFA login challenges deleted by the nightly cleanup",
)
_last_purge_ran_gauge = _meter.create_gauge(
    name="last_purge_ran_at",
    description="Unix timestamp of the last successful nightly cleanup run",
    unit="s",
)


async def nightly_cleanup_task() -> dict:
    """Nightly data-hygiene dispatcher.

    Runs nine independent sub-tasks in sequence; a failure in one does not
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
        purge_expired_email_outbox,
        purge_expired_login_throttle,
        purge_expired_mfa_challenges,
        purge_unactivated_candidate_users,
        redact_expired_email_outbox,
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
    results["redact_email_outbox"] = await _run(
        "redact_email_outbox", redact_expired_email_outbox
    )
    results["purge_email_outbox"] = await _run(
        "purge_email_outbox", purge_expired_email_outbox
    )
    results["purge_login_throttle"] = await _run(
        "purge_login_throttle", purge_expired_login_throttle
    )
    results["purge_mfa_challenges"] = await _run(
        "purge_mfa_challenges", purge_expired_mfa_challenges
    )

    attrs_env = {"environment": settings.environment}
    _purged_counter.add(results["purge_expired_candidates"] or 0, attrs_env)
    _unactivated_users_counter.add(results["purge_unactivated_users"] or 0, attrs_env)
    _export_zips_counter.add(results["purge_export_zips"] or 0, attrs_env)
    _deletion_tokens_counter.add(results["purge_deletion_tokens"] or 0, attrs_env)
    _activation_tokens_counter.add(results["purge_activation_tokens"] or 0, attrs_env)
    _outbox_redacted_counter.add(results["redact_email_outbox"] or 0, attrs_env)
    _outbox_purged_counter.add(results["purge_email_outbox"] or 0, attrs_env)
    _login_throttle_purged_counter.add(results["purge_login_throttle"] or 0, attrs_env)
    _mfa_challenges_purged_counter.add(results["purge_mfa_challenges"] or 0, attrs_env)
    if any(v is not None for v in results.values()):
        _last_purge_ran_gauge.set(time.time(), attrs_env)

    logger.info("nightly_cleanup_complete", extra=results)
    return results


async def send_admin_digest_task() -> int:
    """Daily digest of new applications to the admins.

    Triggered at 08:00 Asia/Jerusalem by EventBridge Scheduler → SQS (task key
    ``send_admin_digest``; the schedule lives in rs-recruiting-infra). Replaces
    the per-application admin email. Idempotent per Israel calendar day via the
    outbox ``dedup_key``, so an SQS redelivery cannot send a second digest.

    Failures propagate on purpose: the message goes back to SQS for retry
    (eventually the DLQ, which alerts), instead of being acked and the day's
    digest silently skipped. Returns the number of applications in the digest.
    """
    from rs_shared.services.admin.application_digest import send_application_digest

    async with async_session() as session:
        async with transactional(session):
            return await send_application_digest(session)
