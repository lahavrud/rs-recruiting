"""Unit tests for database query helpers."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.database_helpers import get_by_id, get_by_id_or_raise
from src.enums import JobStatus
from src.models import CompanyProfile, Job
from src.services.exceptions import JobNotFoundError


@pytest.mark.asyncio
async def test_get_by_id_found(
    session: AsyncSession, company_with_user: CompanyProfile
):
    assert company_with_user.id is not None
    job = Job(
        company_id=company_with_user.id,
        title="Test Job",
        short_description="Short blurb.",
        description="Description",
        requirements=[{"text": "Req one"}, {"text": "Req two"}],
        tags=[],
        location="Tel Aviv",
        status=JobStatus.PENDING_APPROVAL,
        salary_min=10000,
        salary_max=20000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    result = await get_by_id(session, Job, job.id)
    assert result is not None
    assert result.id == job.id
    assert result.title == "Test Job"


@pytest.mark.asyncio
async def test_get_by_id_not_found(session: AsyncSession):
    result = await get_by_id(session, Job, 999999)
    assert result is None


@pytest.mark.asyncio
async def test_get_by_id_or_raise_found(
    session: AsyncSession, company_with_user: CompanyProfile
):
    assert company_with_user.id is not None
    job = Job(
        company_id=company_with_user.id,
        title="Test Job",
        short_description="Short blurb.",
        description="Description",
        requirements=[{"text": "Req one"}, {"text": "Req two"}],
        tags=[],
        location="Tel Aviv",
        status=JobStatus.PENDING_APPROVAL,
        salary_min=10000,
        salary_max=20000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    result = await get_by_id_or_raise(
        session, Job, job.id, lambda pk: JobNotFoundError(f"Job {pk} not found")
    )
    assert result.id == job.id


@pytest.mark.asyncio
async def test_get_by_id_or_raise_not_found(session: AsyncSession):
    with pytest.raises(JobNotFoundError, match="999999"):
        await get_by_id_or_raise(
            session, Job, 999999, lambda pk: JobNotFoundError(f"Job {pk} not found")
        )


@pytest.mark.asyncio
async def test_get_by_id_or_raise_applies_options(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Eager-loading options passed via `options=` are applied to the query."""
    assert company_with_user.id is not None
    job = Job(
        company_id=company_with_user.id,
        title="Test Job",
        short_description="Short blurb.",
        description="Description",
        requirements=[{"text": "Req one"}],
        tags=[],
        location="Tel Aviv",
        status=JobStatus.PENDING_APPROVAL,
        salary_min=10000,
        salary_max=20000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    session.expunge(job)

    result = await get_by_id_or_raise(
        session,
        Job,
        job.id,
        lambda pk: JobNotFoundError(f"Job {pk} not found"),
        options=[selectinload(Job.company)],  # pyright: ignore[reportArgumentType]
    )

    assert result.id == job.id
    # Relationship should already be loaded without triggering a lazy fetch.
    assert "company" in result.__dict__
    assert result.company is not None
    assert result.company.id == company_with_user.id
