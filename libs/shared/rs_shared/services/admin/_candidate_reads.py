"""Admin candidate reads: the shared serializer and the AI-score rankings.

Split out of ``candidates.py`` to keep it under the 300-line cap. Exercised
end-to-end via tests/services/admin/test_candidates.py.
"""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.infrastructure.database_helpers import get_by_id_or_raise
from rs_shared.core.infrastructure.pagination import CursorPage
from rs_shared.core.matching import cosine_similarity_score
from rs_shared.enums import JobStatus
from rs_shared.models import CandidateProfile, Job
from rs_shared.schemas import CandidateAdminRead, CandidateJobMatchRead, JobRead
from rs_shared.services.admin._filters import candidate_not_deleted
from rs_shared.services.exceptions import CandidateNotFoundError

SCORE_SORT_LIMIT = 200
SELECTIN_USER = selectinload(CandidateProfile.user)  # type: ignore[arg-type]


def to_admin_read(
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


async def list_candidates_by_score(
    session: AsyncSession,
    *,
    q: str | None = None,
    job_id: int | None = None,
    has_account: bool | None = None,
    include_deleted: bool = False,
) -> CursorPage[CandidateAdminRead] | None:
    """Return candidates ranked by cosine similarity to a job, best first.

    Only includes candidates with embeddings. Returns a single non-paginated
    page (next_cursor=None), or ``None`` when there is no `job_id` or the job
    has no embedding, in which case the caller falls back to recency sort.
    """
    job = await session.get(Job, job_id) if job_id is not None else None
    if job is None or job.embedding is None:
        return None

    distance_expr = CandidateProfile.embedding.cosine_distance(job.embedding)
    stmt = select(CandidateProfile, distance_expr.label("dist")).options(SELECTIN_USER)
    stmt = stmt.where(
        CandidateProfile.embedding.is_not(None)  # pyright: ignore[reportArgumentType]
    )
    if not include_deleted:
        stmt = stmt.where(candidate_not_deleted())
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
    stmt = stmt.order_by(distance_expr.asc()).limit(SCORE_SORT_LIMIT)

    rows = (await session.execute(stmt)).all()
    items = [
        to_admin_read(candidate, ai_score=cosine_similarity_score(dist))
        for candidate, dist in rows
    ]
    return CursorPage(items=items, next_cursor=None)


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
