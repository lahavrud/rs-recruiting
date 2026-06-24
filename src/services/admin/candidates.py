"""Admin service functions for candidate management."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.core.matching import cosine_similarity_score
from src.core.services.storage import get_storage_provider
from src.enums import ApplicationStatus, JobStatus
from src.models import Application, AuditLog, CandidateProfile, Job
from src.schemas import (
    CandidateActivityEvent,
    CandidateJobMatchRead,
    CandidateProfileRead,
    JobRead,
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
    q: str | None = None,
) -> CursorPage[CandidateProfileRead]:
    """Return one page of candidate profiles, newest first.

    `q`, when given, case-insensitively substring-matches name/email/phone.
    """
    page_size = clamp_limit(limit)
    base = select(CandidateProfile)
    if q and q.strip():
        term = f"%{q.strip()}%"
        base = base.where(
            or_(
                CandidateProfile.full_name.ilike(term),  # pyright: ignore[reportArgumentType]
                CandidateProfile.email.ilike(term),  # pyright: ignore[reportArgumentType]
                CandidateProfile.phone.ilike(term),  # pyright: ignore[reportArgumentType]
            )
        )
    query = apply_cursor(
        base,
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
    """Live-ranked jobs for a candidate, best score first.

    Computed on demand (cosine distance) against every PUBLISHED, embedded
    job — mirrors ``services.admin.jobs.get_job_candidate_matches``, the
    reverse direction.

    Raises ``CandidateNotFoundError`` if the candidate doesn't exist. Returns
    an empty list if the candidate has no embedding yet (e.g. no resume).
    """
    candidate = await get_by_id_or_raise(
        session,
        CandidateProfile,
        candidate_id,
        lambda pk: CandidateNotFoundError(f"Candidate {pk} not found"),
    )
    if candidate.embedding is None:
        return []

    distance = Job.embedding.cosine_distance(candidate.embedding)
    rows = (
        await session.execute(
            select(Job, distance.label("distance"))
            .where(Job.status == JobStatus.PUBLISHED, Job.embedding.is_not(None))
            .order_by(distance)
            .limit(settings.embedding_top_matches)
        )
    ).all()
    return [
        CandidateJobMatchRead(
            job=JobRead.model_validate(job),
            score=cosine_similarity_score(dist),
        )
        for job, dist in rows
    ]


async def list_candidate_activity(
    candidate_id: int,
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[CandidateActivityEvent]:
    """Activity timeline for a candidate's record pane.

    Aggregates audit rows for the candidate profile itself with rows for
    all of their applications, newest first.

    Raises:
        CandidateNotFoundError: If no candidate with that id exists.
    """
    await get_by_id_or_raise(
        session,
        CandidateProfile,
        candidate_id,
        lambda pk: CandidateNotFoundError(f"Candidate {pk} not found"),
    )

    page_size = clamp_limit(limit)
    application_ids = select(Application.id).where(
        Application.candidate_id == candidate_id  # pyright: ignore[reportArgumentType]
    )
    base = select(AuditLog).where(
        or_(
            and_(
                AuditLog.target_type == "CandidateProfile",  # pyright: ignore[reportArgumentType]
                AuditLog.target_id == candidate_id,  # pyright: ignore[reportArgumentType]
            ),
            and_(
                AuditLog.target_type == "Application",  # pyright: ignore[reportArgumentType]
                AuditLog.target_id.in_(application_ids),  # pyright: ignore[reportArgumentType]
            ),
        )
    )
    query = apply_cursor(
        base,
        sort_col=AuditLog.created_at,  # pyright: ignore[reportArgumentType]
        id_col=AuditLog.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
    )
    rows = list((await session.execute(query)).scalars().all())

    application_target_ids = {
        r.target_id for r in rows if r.target_type == "Application"
    }
    job_titles: dict[int, str] = {}
    if application_target_ids:
        job_titles = dict(
            (
                await session.execute(
                    select(Application.id, Job.title)
                    .join(Job, Application.job_id == Job.id)  # pyright: ignore[reportArgumentType]
                    .where(Application.id.in_(application_target_ids))  # pyright: ignore[reportArgumentType]
                )
            ).all()
        )

    def serialize(row: AuditLog) -> CandidateActivityEvent:
        event = CandidateActivityEvent.model_validate(row)
        if row.target_type == "Application":
            event.job_title = job_titles.get(row.target_id)
        return event

    return build_cursor_page(
        rows,
        serializer=serialize,
        cursor_key=lambda a: (a.created_at, a.id),
        limit=page_size,
    )


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
