"""Admin service functions for candidate management."""

import logging
from typing import Literal

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from src.enums import JobStatus
from src.models import Application, AuditLog, CandidateProfile, Job
from src.schemas import (
    CandidateActivityEvent,
    CandidateJobMatchRead,
    CandidateProfileRead,
    JobRead,
)
from src.services.admin._candidates_purge import (
    CANDIDATE_RETENTION_DAYS as CANDIDATE_RETENTION_DAYS,
)
from src.services.admin._candidates_purge import (
    purge_expired_candidates as purge_expired_candidates,
)
from src.services.exceptions import CandidateNotFoundError
from src.services.utils.audit import record_audit_event

_logger = logging.getLogger(__name__)


_SCORE_SORT_LIMIT = 200


async def list_candidates(
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
    q: str | None = None,
    sort: Literal["name", "created_at", "score"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    job_id: int | None = None,
) -> CursorPage[CandidateProfileRead]:
    """Return one page of candidate profiles, sorted by `sort`/`order`.

    `q`, when given, case-insensitively substring-matches name/email/phone.
    `sort="score"` requires `job_id` — ranks candidates by cosine similarity
    to the specified job's embedding; returns a single non-paginated page.
    """
    if sort == "score":
        return await _list_candidates_by_score(
            session, q=q, job_id=job_id, limit=limit, cursor=cursor
        )

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
    rows = (await session.execute(query)).scalars().all()
    return build_cursor_page(
        list(rows),
        serializer=CandidateProfileRead.model_validate,
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
) -> CursorPage[CandidateProfileRead]:
    """Return candidates ranked by cosine similarity to a job, best first.

    Only includes candidates with embeddings. Falls back to recency sort when
    no `job_id` is given or the job has no embedding.
    Returns a single non-paginated page (next_cursor=None).
    """
    job = await session.get(Job, job_id) if job_id is not None else None
    if job is None or job.embedding is None:
        return await list_candidates(
            session, sort="created_at", order="desc", q=q, limit=limit, cursor=cursor
        )

    distance_expr = CandidateProfile.embedding.cosine_distance(job.embedding)
    stmt = (
        select(CandidateProfile, distance_expr.label("dist")).where(
            CandidateProfile.embedding.is_not(None)
        )  # pyright: ignore[reportArgumentType]
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
    items: list[CandidateProfileRead] = []
    for candidate, dist in rows:
        schema = CandidateProfileRead.model_validate(candidate)
        schema.ai_score = cosine_similarity_score(dist)
        items.append(schema)
    return CursorPage(items=items, next_cursor=None)


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
