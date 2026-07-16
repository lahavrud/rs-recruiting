"""Unit tests for job service layer."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.enums import ApplicationStatus, JobStatus, UserRole
from rs_shared.models import Application, CandidateProfile, CompanyProfile, Job, User
from rs_shared.schemas import JobCreate, JobUpdate
from rs_shared.services.company.jobs import (
    create_job,
    delete_job,
    get_job,
    list_company_jobs,
    update_application_status,
    update_job,
)
from rs_shared.services.exceptions import (
    CompanyNotFoundError,
    InvalidApplicationStatusTransitionError,
    JobCannotBeDeletedError,
    JobCannotBeUpdatedError,
    JobNotFoundError,
    JobNotOwnedByCompanyError,
)


@pytest.fixture
async def admin_user(session: AsyncSession) -> User:
    """Create an admin user for testing."""
    user = User(
        email="admin@test.com",
        hashed_password="hashed",
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def job(session: AsyncSession, company_with_user: CompanyProfile) -> Job:
    """Create a job for testing."""
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
@patch("rs_shared.services.company.jobs.enqueue_email_task")
@patch("rs_shared.services.company.jobs.get_all_admin_emails")
async def test_create_job_success(
    mock_get_admin_emails: AsyncMock,
    mock_enqueue_email: AsyncMock,
    session: AsyncSession,
    company_with_user: CompanyProfile,
):
    """Test creating a job successfully."""
    mock_enqueue_email.return_value = "test-job-id"
    mock_get_admin_emails.return_value = ["admin@test.com"]
    assert company_with_user.id is not None

    job_data = JobCreate(
        title="Senior Python Developer",
        short_description="Short blurb for testing.",
        description="We are looking for a senior Python developer...",
        requirements=[
            {"text": "5+ years experience with Python, FastAPI, PostgreSQL"},
            {"text": "Req 2"},
            {"text": "Req 3"},
        ],
        location="Tel Aviv, Israel",
        salary_min=20000,
        salary_max=30000,
    )

    async with transactional(session):
        result = await create_job(job_data, company_with_user.id, session)

    assert result.id is not None
    assert result.title == "Senior Python Developer"
    assert result.status == JobStatus.PENDING_APPROVAL
    assert result.company_id == company_with_user.id

    # Verify job was saved to database
    db_job = await session.get(Job, result.id)
    assert db_job is not None
    assert db_job.title == "Senior Python Developer"

    # Verify email was sent to admins (fires via defer_after_commit after commit)
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
async def test_create_job_company_not_found(session: AsyncSession):
    """Test creating a job with non-existent company."""
    job_data = JobCreate(
        title="Senior Python Developer",
        short_description="Short blurb for testing.",
        description="Description",
        requirements=[{"text": "Requirements"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="Location",
        salary_min=10000,
        salary_max=15000,
    )

    with pytest.raises(CompanyNotFoundError, match="Company with ID 999 not found"):
        await create_job(job_data, 999, session)


@pytest.mark.asyncio
async def test_get_job_success(session: AsyncSession, pending_job: Job):
    """Test getting a job by ID."""
    assert pending_job.id is not None
    result = await get_job(pending_job.id, session)

    assert result.id == pending_job.id
    assert result.title == pending_job.title
    assert result.status == pending_job.status


@pytest.mark.asyncio
async def test_get_job_not_found(session: AsyncSession):
    """Test getting a non-existent job."""
    with pytest.raises(JobNotFoundError, match="Job with ID 999 not found"):
        await get_job(999, session)


@pytest.mark.asyncio
async def test_list_company_jobs(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Test listing jobs for a company."""
    assert company_with_user.id is not None
    # Create multiple jobs
    job1 = Job(
        company_id=company_with_user.id,
        title="Job 1",
        short_description="Short blurb for testing.",
        description="Description 1",
        requirements=[{"text": "Requirements 1"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="Location 1",
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
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job1)
    session.add(job2)
    await session.commit()

    page = await list_company_jobs(company_with_user.id, session)

    assert len(page.items) == 2
    assert page.items[0].title in ["Job 1", "Job 2"]
    assert page.items[1].title in ["Job 1", "Job 2"]


@pytest.mark.asyncio
@patch("rs_shared.services.company.jobs.enqueue_email_task")
@patch("rs_shared.services.company.jobs.get_all_admin_emails")
async def test_update_job_success(
    mock_get_admin_emails: AsyncMock,
    mock_enqueue_email: AsyncMock,
    session: AsyncSession,
    job: Job,
    company_with_user: CompanyProfile,
):
    """Test updating a job successfully."""
    mock_enqueue_email.return_value = "test-job-id"
    mock_get_admin_emails.return_value = ["admin@test.com"]
    assert job.id is not None
    assert company_with_user.id is not None

    job_data = JobUpdate(title="Updated Title", location="Updated Location")

    async with transactional(session):
        result = await update_job(job.id, job_data, company_with_user.id, session)

    assert result.title == "Updated Title"
    assert result.location == "Updated Location"
    assert result.description == job.description  # Unchanged

    # Verify job was updated in database
    db_job = await session.get(Job, job.id)
    assert db_job is not None
    assert db_job.title == "Updated Title"
    assert db_job.location == "Updated Location"

    # Verify email was sent to admins (fires via defer_after_commit after commit)
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
async def test_update_job_not_found(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Test updating a non-existent job."""
    assert company_with_user.id is not None
    job_data = JobUpdate(title="Updated Title")

    with pytest.raises(JobNotFoundError, match="Job with ID 999 not found"):
        await update_job(999, job_data, company_with_user.id, session)


@pytest.mark.asyncio
async def test_update_job_not_owned(
    session: AsyncSession,
    job: Job,
    company_with_user: CompanyProfile,
):
    """Test updating a job not owned by the company."""
    assert job.id is not None
    # Create another company
    other_user = User(
        email="other@test.com",
        hashed_password="hashed",
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(other_user)
    await session.flush()
    assert other_user.id is not None

    other_company = CompanyProfile(
        user_id=other_user.id,
        name="Other Company",
        company_id="123456789",
        address="רח׳ הדוגמה 1, תל אביב",
        contact_email=other_user.email,
        contact_first_name="ישראל",
        contact_last_name="ישראלי",
        contact_mobile_phone="0501234567",
    )
    session.add(other_company)
    await session.commit()
    await session.refresh(other_company)
    assert other_company.id is not None

    job_data = JobUpdate(title="Updated Title")

    with pytest.raises(
        JobNotOwnedByCompanyError,
        match=f"Job {job.id} is not owned by company {other_company.id}",
    ):
        await update_job(job.id, job_data, other_company.id, session)


@pytest.mark.asyncio
async def test_update_job_cannot_be_updated_closed(
    session: AsyncSession,
    job: Job,
    company_with_user: CompanyProfile,
):
    """Test updating a job with CLOSED status."""
    assert job.id is not None
    assert company_with_user.id is not None
    # Set job status to CLOSED
    job.status = JobStatus.CLOSED
    await session.commit()

    job_data = JobUpdate(title="Updated Title")

    with pytest.raises(
        JobCannotBeUpdatedError,
        match=f"Job {job.id} with status JobStatus.CLOSED cannot be updated",
    ):
        await update_job(job.id, job_data, company_with_user.id, session)


@pytest.mark.asyncio
async def test_update_job_cannot_change_status(
    session: AsyncSession,
    job: Job,
    company_with_user: CompanyProfile,
):
    """Test that companies cannot change job status."""
    assert job.id is not None
    assert company_with_user.id is not None
    job_data = JobUpdate(status=JobStatus.PUBLISHED)

    with pytest.raises(
        JobCannotBeUpdatedError,
        match="Companies cannot change job status",
    ):
        await update_job(job.id, job_data, company_with_user.id, session)


@pytest.mark.asyncio
async def test_delete_job_success(
    session: AsyncSession,
    job: Job,
    company_with_user: CompanyProfile,
):
    """Test deleting a job successfully."""
    assert job.id is not None
    assert company_with_user.id is not None
    job_id = job.id
    await delete_job(job_id, company_with_user.id, session)
    await session.commit()

    # Verify job was deleted
    db_job = await session.get(Job, job_id)
    assert db_job is None


@pytest.mark.asyncio
async def test_delete_job_not_found(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Test deleting a non-existent job."""
    assert company_with_user.id is not None
    with pytest.raises(JobNotFoundError, match="Job with ID 999 not found"):
        await delete_job(999, company_with_user.id, session)


@pytest.mark.asyncio
async def test_delete_job_not_owned(
    session: AsyncSession,
    job: Job,
    company_with_user: CompanyProfile,
):
    """Test deleting a job not owned by the company."""
    assert job.id is not None
    # Create another company
    other_user = User(
        email="other@test.com",
        hashed_password="hashed",
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(other_user)
    await session.flush()
    assert other_user.id is not None

    other_company = CompanyProfile(
        user_id=other_user.id,
        name="Other Company",
        company_id="123456789",
        address="רח׳ הדוגמה 1, תל אביב",
        contact_email=other_user.email,
        contact_first_name="ישראל",
        contact_last_name="ישראלי",
        contact_mobile_phone="0501234567",
    )
    session.add(other_company)
    await session.commit()
    await session.refresh(other_company)
    assert other_company.id is not None

    with pytest.raises(
        JobNotOwnedByCompanyError,
        match=f"Job {job.id} is not owned by company {other_company.id}",
    ):
        await delete_job(job.id, other_company.id, session)


@pytest.mark.asyncio
async def test_delete_job_cannot_be_deleted_published(
    session: AsyncSession,
    job: Job,
    company_with_user: CompanyProfile,
):
    """Test deleting a job with PUBLISHED status."""
    assert job.id is not None
    assert company_with_user.id is not None
    # Set job status to PUBLISHED
    job.status = JobStatus.PUBLISHED
    await session.commit()

    with pytest.raises(
        JobCannotBeDeletedError,
        match="cannot be deleted. Only jobs with PENDING_APPROVAL status",
    ):
        await delete_job(job.id, company_with_user.id, session)


@pytest.mark.asyncio
async def test_delete_job_cannot_be_deleted_closed(
    session: AsyncSession,
    job: Job,
    company_with_user: CompanyProfile,
):
    """Test deleting a job with CLOSED status."""
    assert job.id is not None
    assert company_with_user.id is not None
    # Set job status to CLOSED
    job.status = JobStatus.CLOSED
    await session.commit()

    with pytest.raises(
        JobCannotBeDeletedError,
        match="cannot be deleted. Only jobs with PENDING_APPROVAL status",
    ):
        await delete_job(job.id, company_with_user.id, session)


# ==================== company application-status transitions ====================


async def _make_approved_application(session: AsyncSession, job: Job) -> Application:
    """A candidate + APPROVED_BY_ADMIN application (i.e. pushed to the employer)."""
    candidate = CandidateProfile(
        full_name="Dana Applicant",
        email="dana@applicant.com",
        phone="0501234567",
    )
    session.add(candidate)
    await session.flush()
    app = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        status=ApplicationStatus.APPROVED_BY_ADMIN,
    )
    session.add(app)
    await session.commit()
    await session.refresh(app)
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target",
    [
        ApplicationStatus.INTERVIEWING,
        ApplicationStatus.OFFER,
        ApplicationStatus.HIRED,
        ApplicationStatus.REJECTED_BY_COMPANY,
    ],
)
async def test_company_can_set_pipeline_status(
    session: AsyncSession, job: Job, company_with_user: CompanyProfile, target
):
    """Employers may advance/decide across their own pipeline statuses."""
    assert company_with_user.id is not None
    app = await _make_approved_application(session, job)

    result = await update_application_status(
        job.id, app.id, target.value, company_with_user.id, session
    )

    assert result.status == target.value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target",
    [
        ApplicationStatus.APPROVED_BY_ADMIN,
        ApplicationStatus.REJECTED_BY_ADMIN,
        ApplicationStatus.PENDING_ADMIN_REVIEW,
        ApplicationStatus.JOB_CLOSED,
    ],
)
async def test_company_cannot_set_non_settable_status(
    session: AsyncSession, job: Job, company_with_user: CompanyProfile, target
):
    """Admin-owned / intake statuses are not employer-settable."""
    assert company_with_user.id is not None
    app = await _make_approved_application(session, job)

    with pytest.raises(InvalidApplicationStatusTransitionError):
        await update_application_status(
            job.id, app.id, target.value, company_with_user.id, session
        )


@pytest.mark.asyncio
async def test_company_rejects_unknown_status(
    session: AsyncSession, job: Job, company_with_user: CompanyProfile
):
    """A garbage status string is rejected, not coerced."""
    assert company_with_user.id is not None
    app = await _make_approved_application(session, job)

    with pytest.raises(InvalidApplicationStatusTransitionError):
        await update_application_status(
            job.id, app.id, "NONSENSE", company_with_user.id, session
        )
