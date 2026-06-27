"""Admin global match feed — ranked (candidate, job) pairs with no application."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.matching import cosine_similarity_score
from src.enums import ApplicationStatus, JobStatus, MatchSuggestionStatus
from src.models import Application, CandidateProfile, Job, MatchSuggestion
from src.schemas import (
    ApplicationRead,
    ApplicationWithDetails,
    CandidateProfileRead,
    GlobalMatchRead,
)
from src.schemas.jobs import JobRead
from src.services.exceptions import ApplicationAlreadyExistsError

_CANDIDATE_POOL = 30
_JOBS_PER_CANDIDATE = 3
_MIN_SCORE = 0.55
_HOT_SCORE_THRESHOLD = 0.55
_HOT_OVERSAMPLE = 3


async def get_global_matches(
    session: AsyncSession, limit: int = 20
) -> list[GlobalMatchRead]:
    """Return top (candidate, job) pairs ranked by cosine similarity.

    Scans the most recently joined candidates with embeddings, finds their
    top job matches, filters pairs where an application already exists or an
    admin has already acted on the suggestion, and returns the globally
    highest-scoring pairs.
    """
    candidates = (
        (
            await session.execute(
                select(CandidateProfile)
                .where(CandidateProfile.embedding.is_not(None))
                .order_by(CandidateProfile.created_at.desc())
                .limit(_CANDIDATE_POOL)
            )
        )
        .scalars()
        .all()
    )

    if not candidates:
        return []

    candidate_ids = [c.id for c in candidates]

    applied_pairs: set[tuple[int, int]] = {
        (r[0], r[1])
        for r in (
            await session.execute(
                select(Application.candidate_id, Application.job_id).where(
                    Application.candidate_id.in_(candidate_ids)  # type: ignore[arg-type]
                )
            )
        ).all()
    }

    acted_pairs: set[tuple[int, int]] = {
        (r[0], r[1])
        for r in (
            await session.execute(
                select(MatchSuggestion.candidate_id, MatchSuggestion.job_id).where(
                    MatchSuggestion.candidate_id.in_(candidate_ids)  # type: ignore[arg-type]
                )
            )
        ).all()
    }

    excluded = applied_pairs | acted_pairs

    collected: list[tuple[CandidateProfile, Job, float]] = []
    for candidate in candidates:
        distance = Job.embedding.cosine_distance(candidate.embedding)
        rows = (
            await session.execute(
                select(Job, distance.label("dist"))
                .options(selectinload(Job.company))
                .where(Job.status == JobStatus.PUBLISHED, Job.embedding.is_not(None))
                .order_by(distance)
                .limit(_JOBS_PER_CANDIDATE)
            )
        ).all()
        for job, dist in rows:
            if (candidate.id, job.id) not in excluded:
                score = cosine_similarity_score(dist)
                if score >= _MIN_SCORE:
                    collected.append((candidate, job, score))

    collected.sort(key=lambda x: x[2], reverse=True)
    return [
        GlobalMatchRead(
            candidate=CandidateProfileRead.model_validate(c),
            job=JobRead.model_validate(j),
            score=s,
        )
        for c, j, s in collected[:limit]
    ]


async def push_match(
    candidate_id: int,
    job_id: int,
    score: float,
    admin_id: int,
    session: AsyncSession,
) -> ApplicationRead:
    """Create an admin-initiated application from a match suggestion.

    Records a PUSHED MatchSuggestion so the pair is permanently excluded from
    the feed, then creates the Application.

    Raises:
        ApplicationAlreadyExistsError: If a non-withdrawn application already exists.
    """
    existing = (
        await session.execute(
            select(Application).where(
                Application.candidate_id == candidate_id,  # type: ignore[arg-type]
                Application.job_id == job_id,  # type: ignore[arg-type]
                Application.status != ApplicationStatus.WITHDRAWN,  # type: ignore[arg-type]
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ApplicationAlreadyExistsError(job_id=job_id, candidate_id=candidate_id)

    existing_suggestion = (
        await session.execute(
            select(MatchSuggestion).where(
                MatchSuggestion.candidate_id == candidate_id,  # type: ignore[arg-type]
                MatchSuggestion.job_id == job_id,  # type: ignore[arg-type]
            )
        )
    ).scalar_one_or_none()
    if existing_suggestion is not None:
        existing_suggestion.status = MatchSuggestionStatus.PUSHED
        existing_suggestion.acted_by_admin_id = admin_id
        existing_suggestion.score = score
    else:
        session.add(
            MatchSuggestion(
                candidate_id=candidate_id,
                job_id=job_id,
                score=score,
                status=MatchSuggestionStatus.PUSHED,
                acted_by_admin_id=admin_id,
            )
        )
    application = Application(
        job_id=job_id,
        candidate_id=candidate_id,
        status=ApplicationStatus.NEW,
        pushed_by_admin_id=admin_id,
    )
    session.add(application)
    await session.flush()
    return ApplicationRead.model_validate(application)


async def dismiss_match(
    candidate_id: int,
    job_id: int,
    score: float,
    admin_id: int,
    session: AsyncSession,
) -> None:
    """Record an admin decision to dismiss a match suggestion.

    Inserts a DISMISSED MatchSuggestion so the pair is permanently excluded
    from the feed on subsequent loads.
    """
    existing_suggestion = (
        await session.execute(
            select(MatchSuggestion).where(
                MatchSuggestion.candidate_id == candidate_id,  # type: ignore[arg-type]
                MatchSuggestion.job_id == job_id,  # type: ignore[arg-type]
            )
        )
    ).scalar_one_or_none()
    if existing_suggestion is None:
        session.add(
            MatchSuggestion(
                candidate_id=candidate_id,
                job_id=job_id,
                score=score,
                status=MatchSuggestionStatus.DISMISSED,
                acted_by_admin_id=admin_id,
            )
        )
    elif existing_suggestion.status != MatchSuggestionStatus.DISMISSED:
        existing_suggestion.status = MatchSuggestionStatus.DISMISSED
        existing_suggestion.acted_by_admin_id = admin_id
    await session.flush()


async def get_hot_applications(
    session: AsyncSession, limit: int = 10
) -> list[ApplicationWithDetails]:
    """Return top NEW applications ranked by AI match score.

    Only includes pairs where both the candidate and job have embeddings,
    and the computed score is at or above _HOT_SCORE_THRESHOLD.
    """
    distance_expr = CandidateProfile.embedding.cosine_distance(Job.embedding)
    stmt = (
        select(Application, distance_expr.label("dist"))
        .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)  # pyright: ignore[reportArgumentType]
        .join(Job, Application.job_id == Job.id)  # pyright: ignore[reportArgumentType]
        .options(
            selectinload(Application.job).selectinload(Job.company),  # pyright: ignore[reportArgumentType]
            selectinload(Application.candidate),  # pyright: ignore[reportArgumentType]
        )
        .where(
            CandidateProfile.embedding.is_not(None),  # pyright: ignore[reportArgumentType]
            Job.embedding.is_not(None),  # pyright: ignore[reportArgumentType]
            Application.status == ApplicationStatus.NEW,  # pyright: ignore[reportArgumentType]
        )
        .order_by(distance_expr.asc())
        .limit(limit * _HOT_OVERSAMPLE)
    )
    rows = (await session.execute(stmt)).all()
    results: list[ApplicationWithDetails] = []
    for app, dist in rows:
        score = cosine_similarity_score(dist)
        if score >= _HOT_SCORE_THRESHOLD:
            item = ApplicationWithDetails.model_validate(app)
            item.ai_score = score
            results.append(item)
        if len(results) >= limit:
            break
    return results
