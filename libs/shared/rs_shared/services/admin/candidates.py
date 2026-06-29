"""Admin service functions for candidate management."""

import logging
from typing import Literal

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.infrastructure.database_helpers import get_by_id_or_raise
from rs_shared.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from rs_shared.core.matching import cosine_similarity_score
from rs_shared.core.services.storage import StorageProvider, get_storage_provider
from rs_shared.enums import JobStatus
from rs_shared.models import Application, AuditLog, CandidateProfile, Job, User
from rs_shared.schemas import (
    CandidateActivityEvent,
    CandidateAdminRead,
    CandidateJobMatchRead,
    JobRead,
)
from rs_shared.services.admin._candidates_purge import (
    CANDIDATE_RETENTION_DAYS as CANDIDATE_RETENTION_DAYS,
)
from rs_shared.services.admin._candidates_purge import (
    purge_expired_candidates as purge_expired_candidates,
)
from rs_shared.services.candidate.account_deletion import _scrub_candidate_pii
from rs_shared.services.exceptions import (
    CandidateAlreadyDeletedError,
    CandidateNotFoundError,
)
from rs_shared.services.utils.audit import record_audit_event

_logger = logging.getLogger(__name__)


_SCORE_SORT_LIMIT = 200
_SELECTIN_USER = selectinload(CandidateProfile.user)  # type: ignore[arg-type]


def _to_admin_read(
    profile: CandidateProfile, *, ai_score: float | None = None
) -> CandidateAdminRead:
    """Build a ``CandidateAdminRead`` from an eagerly-loaded profile.

    Requires ``CandidateProfile.user`` to have been loaded via selectinload.
    """
    user = getattr(profile, "user", None)
    return CandidateAdminRead(
        id=profile.id,
        full_name=profile.full_name,
        email=profile.email,
        phone=profile.phone,
        resume_path=profile.resume_path,
        resume_summary=profile.resume_summary,
        linkedin_url=profile.linkedin_url,
        consent_given_at=profile.consent_given_at,
        consent_policy_version=profile.consent_policy_version,
        tos_accepted_at=profile.tos_accepted_at,
        tos_version=profile.tos_version,
        created_at=profile.created_at,
        deleted_at=profile.deleted_at,
        ai_score=ai_score,
        has_account=profile.user_id is not None,
        is_deleted=profile.deleted_at is not None,
        user_email=user.email if user else None,
        user_is_active=user.is_active if user else None,
    )


async def list_candidates(
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
    q: str | None = None,
    sort: Literal["name", "created_at", "score"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    job_id: int | None = None,
    has_account: bool | None = None,
    include_deleted: bool = False,
) -> CursorPage[CandidateAdminRead]:
    """Return one page of candidate profiles, sorted by `sort`/`order`.

    `q`, when given, case-insensitively substring-matches name/email/phone.
    `sort="score"` requires `job_id` — ranks candidates by cosine similarity
    to the specified job's embedding; returns a single non-paginated page.
    `has_account`, when set, filters by account presence (user_id NOT NULL).
    `include_deleted`, when False (default), excludes tombstoned profiles.
    """
    if sort == "score":
        return await _list_candidates_by_score(
            session,
            q=q,
            job_id=job_id,
            limit=limit,
            cursor=cursor,
            has_account=has_account,
            include_deleted=include_deleted,
        )

    page_size = clamp_limit(limit)
    base = select(CandidateProfile).options(_SELECTIN_USER)
    if not include_deleted:
        base = base.where(
            CandidateProfile.deleted_at.is_(None)  # pyright: ignore[reportArgumentType]
        )
    if has_account is True:
        base = base.where(
            CandidateProfile.user_id.is_not(None)  # pyright: ignore[reportArgumentType]
        )
    elif has_account is False:
        base = base.where(
            CandidateProfile.user_id.is_(None)  # pyright: ignore[reportArgumentType]
        )
    if q and q.strip():
        term = f"%{q.strip()}%"
        base = base.where(
            or_(
                CandidateProfile.full_name.ilike(term),  # pyright: ignore[reportArgumentType]
                CandidateProfile.email.ilike(term),  # pyright: ignore[reportArgumentType]
                CandidateProfile.phone.ilike(term),  # pyright: ignore[reportArgumentType]
            )
        )
    sort_col = (
        CandidateProfile.full_name if sort == "name" else CandidateProfile.created_at
    )
    query = apply_cursor(
        base,
        sort_col=sort_col,  # pyright: ignore[reportArgumentType]
        id_col=CandidateProfile.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
        sort_key=sort,
        direction=order,
    )
    rows = list((await session.execute(query)).scalars().all())
    return build_cursor_page(
        rows,
        serializer=_to_admin_read,
        cursor_key=lambda c: (c.full_name if sort == "name" else c.created_at, c.id),
        limit=page_size,
        sort_key=sort,
    )


async def _list_candidates_by_score(
    session: AsyncSession,
    *,
    q: str | None = None,
    job_id: int | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    has_account: bool | None = None,
    include_deleted: bool = False,
) -> CursorPage[CandidateAdminRead]:
    """Return candidates ranked by cosine similarity to a job, best first.

    Only includes candidates with embeddings. Falls back to recency sort when
    no `job_id` is given or the job has no embedding.
    Returns a single non-paginated page (next_cursor=None).
    """
    job = await session.get(Job, job_id) if job_id is not None else None
    if job is None or job.embedding is None:
        return await list_candidates(
            session,
            sort="created_at",
            order="desc",
            q=q,
            limit=limit,
            cursor=cursor,
            has_account=has_account,
            include_deleted=include_deleted,
        )

    distance_expr = CandidateProfile.embedding.cosine_distance(job.embedding)
    stmt = select(CandidateProfile, distance_expr.label("dist")).options(_SELECTIN_USER)
    stmt = stmt.where(
        CandidateProfile.embedding.is_not(None)  # pyright: ignore[reportArgumentType]
    )
    if not include_deleted:
        stmt = stmt.where(
            CandidateProfile.deleted_at.is_(None)  # pyright: ignore[reportArgumentType]
        )
    if has_account is True:
        stmt = stmt.where(
            CandidateProfile.user_id.is_not(None)  # pyright: ignore[reportArgumentType]
        )
    elif has_account is False:
        stmt = stmt.where(
            CandidateProfile.user_id.is_(None)  # pyright: ignore[reportArgumentType]
        )
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                CandidateProfile.full_name.ilike(term),  # pyright: ignore[reportArgumentType]
                CandidateProfile.email.ilike(term),  # pyright: ignore[reportArgumentType]
                CandidateProfile.phone.ilike(term),  # pyright: ignore[reportArgumentType]
            )
        )
    stmt = stmt.order_by(distance_expr.asc()).limit(_SCORE_SORT_LIMIT)

    rows = (await session.execute(stmt)).all()
    items = [
        _to_admin_read(candidate, ai_score=cosine_similarity_score(dist))
        for candidate, dist in rows
    ]
    return CursorPage(items=items, next_cursor=None)


async def get_candidate(candidate_id: int, session: AsyncSession) -> CandidateAdminRead:
    candidate = await get_by_id_or_raise(
        session,
        CandidateProfile,
        candidate_id,
        lambda pk: CandidateNotFoundError(f"Candidate {pk} not found"),
        options=[_SELECTIN_USER],
    )
    return _to_admin_read(candidate)


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
            .options(selectinload(Job.company))
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


async def admin_tombstone_candidate(
    candidate_id: int,
    session: AsyncSession,
    *,
    storage: StorageProvider | None = None,
    actor_user_id: int | None = None,
    ip_address: str | None = None,
) -> None:
    """Admin-initiated GDPR tombstone of a candidate profile.

    Atomically:
    1. Validates the candidate exists and is not already tombstoned.
    2. NULLs ``Application.resume_path`` for all the candidate's applications.
    3. Best-effort: deletes the candidate's resume file from storage.
    4. Scrubs all PII fields on ``CandidateProfile``; sets ``deleted_at``.
    5. Hard-deletes the linked ``User`` row if one exists (FK CASCADE sweeps
       sessions/tokens; FK SET NULL clears ``CandidateProfile.user_id``).
    6. Writes an ``admin_deleted_candidate`` audit event.

    Unlike the self-service flow, no email confirmation is sent.

    Raises:
        CandidateNotFoundError: If no candidate with that id exists.
        CandidateAlreadyDeletedError: If the profile is already tombstoned.
    """
    candidate = await get_by_id_or_raise(
        session,
        CandidateProfile,
        candidate_id,
        lambda pk: CandidateNotFoundError(f"Candidate {pk} not found"),
        options=[_SELECTIN_USER],
    )

    if candidate.deleted_at is not None:
        raise CandidateAlreadyDeletedError(
            f"Candidate {candidate_id} is already tombstoned"
        )

    # NULL application resume snapshots (preserve application rows).
    await session.execute(
        update(Application)
        .where(Application.candidate_id == candidate_id)  # pyright: ignore[reportArgumentType]
        .values(resume_path=None, resume_filename=None, resume_hash=None)
    )

    # Best-effort resume storage delete.
    _storage = storage or get_storage_provider()
    if candidate.resume_path:
        try:
            await _storage.delete_file(candidate.resume_path)
        except Exception:
            _logger.warning(
                "admin_tombstone: storage delete failed for resume %s",
                candidate.resume_path,
            )

    linked_user_id = candidate.user_id

    # Tombstone: scrub all PII, mark deleted.
    _scrub_candidate_pii(candidate)

    # Hard-delete linked User.  FK SET NULL cascade updates profile.user_id;
    # FK CASCADE cleans up RefreshToken, PasswordResetToken, etc.
    if linked_user_id is not None:
        user = await session.get(User, linked_user_id)
        if user is not None:
            await session.delete(user)
            await session.flush()

    await record_audit_event(
        session,
        actor_user_id=actor_user_id,
        action="admin_deleted_candidate",
        target_type="candidateprofile",
        target_id=candidate_id,
        ip_address=ip_address,
    )

    _logger.info("admin_tombstone_candidate", extra={"candidate_id": candidate_id})
