"""Tests for Job model."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import JobStatus
from src.models import CompanyProfile, Job


@pytest.mark.asyncio
async def test_job_creation_with_defaults_sets_pending_approval_status(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Test creating a Job model."""
    assert company_with_user.id is not None
    job = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        short_description="Short blurb for testing.",
        description="We are looking for a senior Python developer...",
        requirements=[
            {"text": "5+ years experience with Python, FastAPI, PostgreSQL"},
            {"text": "Req 2"},
            {"text": "Req 3"},
        ],
        location="Tel Aviv, Israel",
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Verify job was created with correct defaults
    assert job.id is not None
    assert job.title == "Senior Python Developer"
    assert job.status == JobStatus.PENDING_APPROVAL
    assert job.created_at is not None
    assert job.updated_at is not None


@pytest.mark.asyncio
async def test_job_required_fields(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Test that all required fields must be provided."""
    assert company_with_user.id is not None
    # Missing title should fail at Pydantic validation
    with pytest.raises(Exception):  # ValidationError from Pydantic
        job = Job(  # type: ignore[call-arg]
            company_id=company_with_user.id,
            # title is missing - should fail
            description="Description",
            requirements=[
                {"text": "Requirements"},
                {"text": "Req 2"},
                {"text": "Req 3"},
            ],
            location="Location",
        )
        session.add(job)
        await session.commit()


@pytest.mark.asyncio
async def test_job_salary_range_db_constraint_rejects_inverted(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """DB-level CHECK rejects salary_min > salary_max even when bypassing Pydantic."""
    assert company_with_user.id is not None
    job = Job(
        company_id=company_with_user.id,
        title="Test Job",
        short_description="Short blurb for testing.",
        description="d",
        requirements=[{"text": "r"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="l",
        salary_min=20000,
        salary_max=10000,
    )
    session.add(job)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_job_salary_range_db_rejects_null(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """NULL salary_min or salary_max is rejected at the DB level (NOT NULL)."""
    assert company_with_user.id is not None
    job = Job(
        company_id=company_with_user.id,
        title="Test Job",
        short_description="Short blurb for testing.",
        description="d",
        requirements=[{"text": "r"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="l",
        salary_min=15000,
        salary_max=None,  # type: ignore[arg-type]
    )
    session.add(job)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_job_salary_range_db_constraint_allows_equal(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """salary_min == salary_max is allowed (boundary case)."""
    assert company_with_user.id is not None
    job = Job(
        company_id=company_with_user.id,
        title="Test Job",
        short_description="Short blurb for testing.",
        description="d",
        requirements=[{"text": "r"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="l",
        salary_min=15000,
        salary_max=15000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None
