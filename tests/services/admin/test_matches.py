"""Unit tests for the admin match-feed service."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.enums import ApplicationStatus
from rs_shared.models import Application, CandidateProfile, Job
from rs_shared.services.admin.matches import (
    get_global_matches,
    get_hot_applications,
    push_match,
)
from rs_shared.services.exceptions import JobNotFoundError, JobNotPublishedError


@pytest.mark.asyncio
async def test_get_global_matches_empty_db(session: AsyncSession):
    """Returns an empty list when no candidates have embeddings."""
    result = await get_global_matches(session)
    assert result == []


@pytest.mark.asyncio
async def test_get_hot_applications_empty_db(session: AsyncSession):
    """Returns an empty list when no applications exist."""
    result = await get_hot_applications(session)
    assert result == []


# ── push_match job-status guard ───────────────────────────────────────────────


async def _application_count(session: AsyncSession, job_id: int) -> int:
    rows = await session.execute(
        select(Application).where(Application.job_id == job_id)  # pyright: ignore[reportArgumentType]
    )
    return len(list(rows.scalars().all()))


@pytest.mark.asyncio
async def test_push_match_onto_closed_job_rejected(
    session: AsyncSession, closed_job: Job, candidate_profile: CandidateProfile
):
    """A job closed between the feed load and the push must not gain an application.

    The close cascade has already run by then, so an application created here
    would sit active on a closed job with nothing left to sweep it.
    """
    with pytest.raises(JobNotPublishedError):
        await push_match(candidate_profile.id, closed_job.id, 0.9, 1, session)

    assert await _application_count(session, closed_job.id) == 0


@pytest.mark.asyncio
async def test_push_match_onto_pending_job_rejected(
    session: AsyncSession, pending_job: Job, candidate_profile: CandidateProfile
):
    """Only PUBLISHED jobs accept pushes — a pending job is not yet live."""
    with pytest.raises(JobNotPublishedError):
        await push_match(candidate_profile.id, pending_job.id, 0.9, 1, session)

    assert await _application_count(session, pending_job.id) == 0


@pytest.mark.asyncio
async def test_push_match_onto_missing_job_raises(
    session: AsyncSession, candidate_profile: CandidateProfile
):
    with pytest.raises(JobNotFoundError):
        await push_match(candidate_profile.id, 99999, 0.9, 1, session)


@pytest.mark.asyncio
async def test_push_match_onto_published_job_succeeds(
    session: AsyncSession, published_job: Job, candidate_profile: CandidateProfile
):
    """Regression guard — the status check must not block the normal path."""
    result = await push_match(candidate_profile.id, published_job.id, 0.9, 1, session)
    await session.commit()

    assert result.status == ApplicationStatus.PENDING_ADMIN_REVIEW
    assert await _application_count(session, published_job.id) == 1
