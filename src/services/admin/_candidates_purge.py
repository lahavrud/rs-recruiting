"""Retention-purge logic for candidate data.

Split out of candidates.py to satisfy the 300-line file cap.
Exercised end-to-end via tests/services/admin/test_candidates.py.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.services.storage import get_storage_provider
from src.enums import ApplicationStatus, JobStatus
from src.models import Application, CandidateProfile, Job
from src.services.utils.audit import record_audit_event

CANDIDATE_RETENTION_DAYS = 365  # 12 months per privacy policy

_logger = logging.getLogger(__name__)


async def purge_expired_candidates(session: AsyncSession) -> int:
    """Delete candidates whose data is past the 12-month retention window.

    A candidate is purged only when *every* one of their applications meets
    all three conditions:

    - linked Job is CLOSED
    - linked Job.updated_at is more than ``CANDIDATE_RETENTION_DAYS`` ago
    - the application's own status is not HIRED

    A candidate with even one application that is still active, recently
    closed, or HIRED is preserved — companies may still need that data for
    payroll / dispute resolution. New candidates with no applications at
    all are also preserved (no expiry has started).

    Resume files are best-effort deleted from storage before the DB row
    is removed; storage failures are logged and ignored so a partial S3
    outage cannot block compliance deletions.

    Returns the number of candidates purged.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=CANDIDATE_RETENTION_DAYS)

    preserved_ids_subq = (
        select(Application.candidate_id)
        .join(Job, Job.id == Application.job_id)  # pyright: ignore[reportArgumentType]
        .where(
            (Job.status != JobStatus.CLOSED)
            | (Job.updated_at >= cutoff)
            | (Application.status == ApplicationStatus.HIRED)
        )
    ).subquery()

    # Eligible: candidates with at least one application AND zero
    # preserve-flagging applications.
    eligible_query = (
        select(CandidateProfile)
        .join(Application, Application.candidate_id == CandidateProfile.id)  # pyright: ignore[reportArgumentType]
        .where(CandidateProfile.id.notin_(select(preserved_ids_subq)))  # pyright: ignore[attr-defined]
        .distinct()
    )

    candidates = list((await session.execute(eligible_query)).scalars().all())

    storage = get_storage_provider()
    purged = 0
    for candidate in candidates:
        candidate_id = candidate.id
        if candidate.resume_path:
            try:
                deleted = await storage.delete_file(candidate.resume_path)
                if not deleted:
                    _logger.warning(
                        "Storage delete returned False for resume %s during purge — "
                        "file may remain in bucket; check IAM permissions",
                        candidate.resume_path,
                    )
            except Exception:
                _logger.exception(
                    "Failed to delete candidate resume file %s during purge",
                    candidate.resume_path,
                )
        await session.execute(
            delete(Application).where(Application.candidate_id == candidate.id)  # pyright: ignore[reportArgumentType]
        )
        await session.delete(candidate)
        # Audit trail: candidate id only (no PII) — needed to prove the
        # 12-month deletion to a privacy auditor.
        _logger.info("retention.purge candidate_id=%d", candidate_id)
        await record_audit_event(
            session,
            actor_user_id=None,
            action="candidate.purge",
            target_type="CandidateProfile",
            target_id=candidate_id,
        )
        purged += 1

    await session.flush()
    if purged:
        _logger.info("purge_expired_candidates: removed %d candidates", purged)
    return purged
