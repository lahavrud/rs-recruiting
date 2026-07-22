"""Unit tests for admin job approval service functions."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.enums import JobStatus
from rs_shared.models import CompanyProfile, Job, User
from rs_shared.services.admin.jobs_workflow import (
    approve_job,
    contact_job,
    list_pending_jobs,
    reject_job,
)
from rs_shared.services.exceptions import JobNotFoundError, JobNotPendingError


@pytest.fixture
async def pending_job(session: AsyncSession, company_with_user: CompanyProfile) -> Job:
    """Create a pending job for testing."""
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
        status=JobStatus.PENDING_APPROVAL,
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None
    return job


@pytest.mark.asyncio
async def test_list_pending_jobs_empty(session: AsyncSession):
    """Test listing pending jobs when none exist."""
    page = await list_pending_jobs(session)
    assert page.items == []


@pytest.mark.asyncio
async def test_list_pending_jobs(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Test listing pending jobs."""
    # Create multiple pending jobs
    job1 = Job(
        company_id=company_with_user.id,
        title="Job 1",
        short_description="Short blurb for testing.",
        description="Description 1",
        requirements=[{"text": "Requirements 1"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="Location 1",
        status=JobStatus.PENDING_APPROVAL,
        salary_min=15000,
        salary_max=25000,
    )
    job2 = Job(
        company_id=company_with_user.id,
        title="Job 2",
        short_description="Short blurb for testing.",
        description="Description 2",
        requirements=[{"text": "Requirements 2"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="Location 2",
        status=JobStatus.PENDING_APPROVAL,
        salary_min=15000,
        salary_max=25000,
    )
    # Create a published job (should not be included)
    published_job = Job(
        company_id=company_with_user.id,
        title="Published Job",
        short_description="Short blurb for testing.",
        description="Description",
        requirements=[{"text": "Requirements"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="Location",
        status=JobStatus.PUBLISHED,
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job1)
    session.add(job2)
    session.add(published_job)
    await session.commit()

    page = await list_pending_jobs(session)

    assert len(page.items) == 2
    assert all(job.status == JobStatus.PENDING_APPROVAL for job in page.items)
    assert all(job.title in ("Job 1", "Job 2") for job in page.items)


@pytest.mark.asyncio
@patch("rs_shared.services.admin.jobs_workflow.enqueue_email_task")
async def test_approve_job_success(
    mock_enqueue_email: AsyncMock,
    session: AsyncSession,
    pending_job: Job,
):
    """Test approving a job successfully."""
    mock_enqueue_email.return_value = "test-job-id"
    assert pending_job.id is not None

    async with transactional(session):
        result = await approve_job(pending_job.id, session)
    await session.refresh(pending_job)

    assert result.id == pending_job.id
    assert result.status == JobStatus.PUBLISHED
    assert pending_job.status == JobStatus.PUBLISHED

    # Verify email was sent (defer_after_commit fires after transactional commits)
    mock_enqueue_email.assert_called_once()
    call_args = mock_enqueue_email.call_args
    assert call_args.kwargs["to"] == "company@test.com"
    assert "approved" in call_args.kwargs["subject"].lower()
    assert pending_job.title in call_args.kwargs["body"]


@pytest.mark.asyncio
async def test_approve_job_not_found(session: AsyncSession):
    """Test approving a non-existent job."""
    with pytest.raises(JobNotFoundError, match="not found"):
        await approve_job(99999, session)


@pytest.mark.asyncio
async def test_approve_job_already_published(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Test approving an already published job."""
    job = Job(
        company_id=company_with_user.id,
        title="Published Job",
        short_description="Short blurb for testing.",
        description="Description",
        requirements=[{"text": "Requirements"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="Location",
        status=JobStatus.PUBLISHED,
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None

    with pytest.raises(JobNotPendingError, match="not pending"):
        await approve_job(job.id, session)


@pytest.mark.asyncio
@patch("rs_shared.services.admin.jobs_workflow.enqueue_email_task")
async def test_reject_job_success(
    mock_enqueue_email: AsyncMock,
    session: AsyncSession,
    pending_job: Job,
):
    """Test rejecting a job successfully."""
    mock_enqueue_email.return_value = "test-job-id"
    assert pending_job.id is not None

    async with transactional(session):
        await reject_job(pending_job.id, session)
    await session.refresh(pending_job)

    assert pending_job.status == JobStatus.CLOSED
    # Rejection closes the job, so it anchors the retention window too.
    assert pending_job.closed_at is not None

    # Verify email was sent (defer_after_commit fires after transactional commits)
    mock_enqueue_email.assert_called_once()
    call_args = mock_enqueue_email.call_args
    assert call_args.kwargs["to"] == "company@test.com"
    assert "rejected" in call_args.kwargs["subject"].lower()
    assert pending_job.title in call_args.kwargs["body"]


@pytest.mark.asyncio
async def test_reject_job_not_found(session: AsyncSession):
    """Test rejecting a non-existent job."""
    with pytest.raises(JobNotFoundError, match="not found"):
        await reject_job(99999, session)


@pytest.mark.asyncio
async def test_reject_job_already_published(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Test rejecting an already published job."""
    job = Job(
        company_id=company_with_user.id,
        title="Published Job",
        short_description="Short blurb for testing.",
        description="Description",
        requirements=[{"text": "Requirements"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="Location",
        status=JobStatus.PUBLISHED,
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None

    with pytest.raises(JobNotPendingError, match="not pending"):
        await reject_job(job.id, session)


# ── contact_job ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_contact_job_not_found(session: AsyncSession):
    """contact_job raises JobNotFoundError for a non-existent job_id."""
    with pytest.raises(JobNotFoundError):
        await contact_job(99999, "any note", session)


@pytest.mark.asyncio
@patch("rs_shared.services.admin.jobs_workflow.enqueue_email_task")
async def test_contact_job_enqueues_email(
    mock_enqueue: AsyncMock,
    session: AsyncSession,
    pending_job: Job,
    company_with_user: CompanyProfile,
):
    """contact_job routes the email to the job owner and includes the admin note."""
    admin_note = "Please add three more requirements."
    await contact_job(pending_job.id, admin_note, session)
    mock_enqueue.assert_awaited_once()
    owner = (
        await session.execute(select(User).where(User.id == company_with_user.user_id))
    ).scalar_one()
    call_kwargs = mock_enqueue.call_args.kwargs
    assert call_kwargs["to"] == owner.email
    assert admin_note in call_kwargs["body"]


@pytest.mark.asyncio
@patch("rs_shared.services.admin.jobs_workflow.enqueue_email_task")
async def test_contact_job_works_on_published_job(
    mock_enqueue: AsyncMock,
    session: AsyncSession,
    company_with_user: CompanyProfile,
):
    """contact_job accepts any job status — no status guard like approve/reject."""
    job = Job(
        company_id=company_with_user.id,
        title="Published Job",
        short_description="Short blurb for testing.",
        description="Description.",
        requirements=[{"text": "Req 1"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="Tel Aviv",
        status=JobStatus.PUBLISHED,
        salary_min=10000,
        salary_max=20000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None

    await contact_job(job.id, "Following up on this published role.", session)
    mock_enqueue.assert_awaited_once()
