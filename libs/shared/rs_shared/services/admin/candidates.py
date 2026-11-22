"""Admin service functions for candidate management."""

import logging
from typing import Literal

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.database_helpers import get_by_id_or_raise
from rs_shared.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from rs_shared.core.services.storage import StorageProvider, get_storage_provider
from rs_shared.models import Application, AuditLog, CandidateProfile, Job, User
from rs_shared.schemas import (
    CandidateActivityEvent,
    CandidateAdminRead,
)
from rs_shared.services.admin._candidate_reads import (
    SELECTIN_USER,
    list_candidates_by_score,
    to_admin_read,
)
from rs_shared.services.admin._candidate_reads import (
    get_candidate_job_matches as get_candidate_job_matches,
)
from rs_shared.services.admin._candidates_purge import (
    CANDIDATE_RETENTION_DAYS as CANDIDATE_RETENTION_DAYS,
)
from rs_shared.services.admin._candidates_purge import (
    purge_expired_candidates as purge_expired_candidates,
)
from rs_shared.services.admin._filters import candidate_not_deleted
from rs_shared.services.exceptions import (
    CandidateAlreadyDeletedError,
    CandidateNotFoundError,
)
from rs_shared.services.utils.application_audit import deleted_application_ids
from rs_shared.services.utils.audit import record_audit_event
from rs_shared.services.utils.candidate_profiles import scrub_candidate_pii

_logger = logging.getLogger(__name__)


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
        ranked = await list_candidates_by_score(
            session,
            q=q,
            job_id=job_id,
            has_account=has_account,
            include_deleted=include_deleted,
        )
        if ranked is not None:
            return ranked
        # No job, or it has no embedding yet: fall back to recency.
        sort, order = "created_at", "desc"

    page_size = clamp_limit(limit)
    base = select(CandidateProfile).options(SELECTIN_USER)
    if not include_deleted:
        base = base.where(candidate_not_deleted())
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
        serializer=to_admin_read,
        cursor_key=lambda c: (c.full_name if sort == "name" else c.created_at, c.id),
        limit=page_size,
        sort_key=sort,
    )


async def get_candidate(candidate_id: int, session: AsyncSession) -> CandidateAdminRead:
    candidate = await get_by_id_or_raise(
        session,
        CandidateProfile,
        candidate_id,
        lambda pk: CandidateNotFoundError(f"Candidate {pk} not found"),
        options=[SELECTIN_USER],
    )
    return to_admin_read(candidate)


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
                or_(
                    AuditLog.target_id.in_(application_ids),  # pyright: ignore[reportArgumentType]
                    # Deleted applications are gone from Application; their
                    # delete rows still tie them to this candidate.
                    AuditLog.target_id.in_(deleted_application_ids(candidate_id)),  # pyright: ignore[reportArgumentType]
                ),
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
    6. Writes a ``candidate.delete`` audit event.

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
        options=[SELECTIN_USER],
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
    scrub_candidate_pii(candidate)

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
        action="candidate.delete",
        target_type="CandidateProfile",
        target_id=candidate_id,
        ip_address=ip_address,
    )

    _logger.info("admin_tombstone_candidate", extra={"candidate_id": candidate_id})
