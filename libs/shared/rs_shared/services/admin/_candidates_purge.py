"""Retention-purge logic for candidate data.

Split out of candidates.py to satisfy the 300-line file cap.
Exercised end-to-end via tests/services/admin/test_candidates.py.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.services.storage import get_storage_provider
from rs_shared.enums import (
    ACTIVE_APPLICATION_STATUSES,
    ApplicationStatus,
    JobStatus,
)
from rs_shared.models import Application, CandidateProfile, Job, User
from rs_shared.services.utils.audit import record_audit_event

CANDIDATE_RETENTION_DAYS = 365  # 12 months per privacy policy

_logger = logging.getLogger(__name__)


async def purge_expired_candidates(session: AsyncSession) -> int:
    """Delete candidates whose data is past the 12-month retention window.

    A candidate is purged only when *every* one of their applications meets
    all four conditions:

    - linked Job is CLOSED
    - linked Job.closed_at is more than ``CANDIDATE_RETENTION_DAYS`` ago
    - the application's own status is not HIRED
    - the application's own status is not ``is_active``

    The active check is deliberately stated on the application rather than
    inferred from the job. It used to be implicit — an active application was
    assumed to imply a job that is not closed — so an application left in
    flight on a long-closed job silently failed to preserve its candidate, and
    the candidate was purged while the admin pipeline still showed the
    application as live work.

    The window is measured from ``Job.closed_at``, not ``Job.updated_at``:
    ``updated_at`` moves on every edit, so touching a long-closed job used to
    restart the retention clock for everyone who had applied to it. A CLOSED
    job with a NULL ``closed_at`` preserves rather than purges — it should not
    occur (the migration backfills, and every close path stamps it), so it
    means the anchor is unknown, and over-retaining is the safe reading.

    A candidate with even one application that is still active, recently
    closed, or HIRED is preserved — companies may still need that data for
    payroll / dispute resolution. New candidates with no applications at
    all are also preserved (no expiry has started).

    Resume files are best-effort deleted from storage before the DB row
    is removed; storage failures are logged and ignored so a partial S3
    outage cannot block compliance deletions.

    Each purged candidate's backing User (if any) is deleted too, so the
    purge never leaves an orphaned candidate-role account behind.

    Returns the number of candidates purged.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=CANDIDATE_RETENTION_DAYS)

    # The job's retention window has run out. Stated positively and once: only
    # a CLOSED job with a known anchor older than the cutoff can expire, so a
    # NULL anchor simply fails this test rather than needing its own clause.
    job_window_expired = (
        (Job.status == JobStatus.CLOSED)
        & (Job.closed_at.is_not(None))
        & (Job.closed_at < cutoff)
    )

    preserved_ids_subq = (
        select(Application.candidate_id)
        .join(Job, Job.id == Application.job_id)  # pyright: ignore[reportArgumentType]
        .where(
            ~job_window_expired
            | (Application.status == ApplicationStatus.HIRED)
            | (Application.status.in_(ACTIVE_APPLICATION_STATUSES))  # type: ignore[arg-type]
        )
    ).subquery()

    # Eligible: candidates with at least one application AND zero
    # preserve-flagging applications. Tombstoned profiles are excluded —
    # their Application rows must survive for recruiting-history purposes.
    eligible_query = (
        select(CandidateProfile)
        .join(Application, Application.candidate_id == CandidateProfile.id)  # pyright: ignore[reportArgumentType]
        .where(
            CandidateProfile.id.notin_(select(preserved_ids_subq)),  # pyright: ignore[attr-defined]
            CandidateProfile.deleted_at.is_(None),
        )
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
        user_id = candidate.user_id
        await session.delete(candidate)
        # Also remove the backing User so no orphaned candidate-role account
        # survives the purge (it would still authenticate but 404 everywhere and
        # keep the email "taken"). The User's auth/token rows DB-cascade.
        if user_id is not None:
            user = await session.get(User, user_id)
            if user is not None:
                await session.delete(user)
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
