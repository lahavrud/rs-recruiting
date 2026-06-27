"""Candidate recommendation sub-module for company job service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.core.matching import cosine_similarity_score
from src.models import Application, CandidateProfile, Job
from src.schemas.companies import CompanyJobRecommendationRead
from src.services.exceptions import JobNotFoundError, JobNotOwnedByCompanyError

_RECOMMENDATION_POOL = 50
_RECOMMENDATION_LIMIT = 10
_RECOMMENDATION_MIN_SCORE = 0.50


async def get_job_recommendations(
    job_id: int,
    company_id: int,
    session: AsyncSession,
) -> list[CompanyJobRecommendationRead]:
    """Return AI-ranked candidate recommendations for a published company job.

    Finds candidates with embeddings who have NOT already applied, ranked by
    cosine similarity to the job's embedding. Returns an empty list when the
    job has no embedding yet (not yet published or not yet indexed).

    Raises:
        JobNotFoundError: If job not found
        JobNotOwnedByCompanyError: If job is not owned by the company
    """
    job = await get_by_id_or_raise(
        session, Job, job_id, lambda pk: JobNotFoundError(f"Job with ID {pk} not found")
    )
    if job.company_id != company_id:
        raise JobNotOwnedByCompanyError(
            f"Job {job_id} is not owned by company {company_id}"
        )
    if job.embedding is None:
        return []

    applied_candidate_ids: set[int] = {
        row[0]
        for row in (
            await session.execute(
                select(Application.candidate_id).where(Application.job_id == job_id)  # pyright: ignore[reportArgumentType]
            )
        ).all()
    }

    distance = CandidateProfile.embedding.cosine_distance(job.embedding)
    rows = (
        await session.execute(
            select(CandidateProfile, distance.label("dist"))
            .where(
                CandidateProfile.embedding.is_not(None),  # pyright: ignore[reportArgumentType]
                ~CandidateProfile.id.in_(applied_candidate_ids),  # pyright: ignore[reportArgumentType]
            )
            .order_by(distance)
            .limit(_RECOMMENDATION_POOL)
        )
    ).all()

    results: list[CompanyJobRecommendationRead] = []
    for candidate, dist in rows:
        score = cosine_similarity_score(dist)
        if score < _RECOMMENDATION_MIN_SCORE:
            break
        results.append(
            CompanyJobRecommendationRead(
                candidate_id=candidate.id or 0,
                full_name=candidate.full_name,
                email=candidate.email,
                phone=candidate.phone,
                score=score,
            )
        )
        if len(results) >= _RECOMMENDATION_LIMIT:
            break
    return results
