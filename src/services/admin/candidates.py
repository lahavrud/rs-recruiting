"""Admin service functions for candidate management."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.core.services.storage import get_storage_provider
from src.enums import ApplicationStatus, JobStatus
from src.models import Application, CandidateProfile, Job, JobMatch
from src.schemas import (
    CandidateJobMatchRead,
    CandidateProfileRead,
    CandidateProfileUpdate,
)
from src.services.exceptions import CandidateNotFoundError
from src.services.utils.audit import record_audit_event

CANDIDATE_RETENTION_DAYS = 365  # 12 months per privacy policy

_logger = logging.getLogger(__name__)


async def list_candidates(
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[CandidateProfileRead]:
    page_size = clamp_limit(limit)
    query = apply_cursor(
        select(CandidateProfile),
        sort_col=CandidateProfile.created_at,  # pyright: ignore[reportArgumentType]
        id_col=CandidateProfile.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
    )
    rows = (await session.execute(query)).scalars().all()
    return build_cursor_page(
        list(rows),
        serializer=CandidateProfileRead.model_validate,
        cursor_key=lambda c: (c.created_at, c.id),
        limit=page_size,
    )


async def get_candidate(
    candidate_id: int, session: AsyncSession
) -> CandidateProfileRead:
    candidate = await get_by_id_or_raise(
        session,
        CandidateProfile,
        candidate_id,
        lambda pk: CandidateNotFoundError(f"Candidate {pk} not found"),
    )
    return CandidateProfileRead.model_validate(candidate)


async def get_candidate_job_matches(
    candidate_id: int, session: AsyncSession
) -> list[CandidateJobMatchRead]:
    """Return the candidate's persisted job matches, best score first.

    Raises ``CandidateNotFoundError`` if the candidate doesn't exist (an empty
    list means the candidate exists but has no matches yet — e.g. no resume).
    """
    await get_by_id_or_raise(
        session,
        CandidateProfile,
        candidate_id,
        lambda pk: CandidateNotFoundError(f"Candidate {pk} not found"),
    )
    rows = (
        (
            await session.execute(
                select(JobMatch)
                .options(selectinload(JobMatch.job))
                .where(JobMatch.candidate_id == candidate_id)
                .order_by(JobMatch.score.desc())
            )
        )
        .scalars()
        .all()
    )
    return [CandidateJobMatchRead.model_validate(row) for row in rows]


async def update_candidate(
    candidate_id: int,
    data: CandidateProfileUpdate,
    session: AsyncSession,
) -> CandidateProfileRead:
    candidate = await get_by_id_or_raise(
        session,
        CandidateProfile,
        candidate_id,
        lambda pk: CandidateNotFoundError(f"Candidate {pk} not found"),
    )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(candidate, field, value)

    await session.flush()
    await session.refresh(candidate)
    return CandidateProfileRead.model_validate(candidate)


async def delete_candidate(
    candidate_id: int,
    session: AsyncSession,
    *,
    actor_user_id: int | None = None,
    ip_address: str | None = None,
) -> None:
    """Hard-delete a candidate, cascading through their applications.

    Best-effort delete of the latest resume snapshot from storage. Failures
    on the storage delete are logged and ignored — DB state stays consistent.

    Raises:
        CandidateNotFoundError: If no candidate with that id exists.
    """
    candidate = await get_by_id_or_raise(
        session,
        CandidateProfile,
        candidate_id,
        lambda pk: CandidateNotFoundError(f"Candidate {pk} not found"),
    )

    await session.execute(
        delete(Application).where(Application.candidate_id == candidate_id)  # pyright: ignore[reportArgumentType]
    )

    if candidate.resume_path:
        try:
            deleted = await get_storage_provider().delete_file(candidate.resume_path)
            if not deleted:
                _logger.warning(
                    "Storage delete returned False for resume %s — "
                    "file may remain in bucket; check IAM permissions",
                    candidate.resume_path,
                )
        except Exception:
            _logger.exception(
                "Failed to delete candidate resume file %s", candidate.resume_path
            )

    await session.delete(candidate)
    await session.flush()

    await record_audit_event(
        session,
        actor_user_id=actor_user_id,
        action="candidate.delete",
        target_type="CandidateProfile",
        target_id=candidate_id,
        ip_address=ip_address,
    )


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

    # Subquery: candidate_ids with at least one application that does NOT
    # meet the purge criteria. Those candidates must be preserved.
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
