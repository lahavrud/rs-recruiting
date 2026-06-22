"""Tests for Application (Match) model."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import ApplicationStatus, JobStatus, UserRole
from src.models import Application, CandidateProfile, CompanyProfile, Job, User


@pytest.fixture
async def job_and_candidate(session: AsyncSession) -> dict[str, Job | CandidateProfile]:
    """Create a job and candidate for testing applications."""
    # Create company with user
    user = User(
        email="company@test.com",
        hashed_password="hashed",
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    company = CompanyProfile(
        user_id=user.id,  # type: ignore[arg-type]
        name="Test Company",
        company_id="123456789",
        address="רח׳ הדוגמה 1, תל אביב",
        contact_email=user.email,
        contact_first_name="ישראל",
        contact_last_name="ישראלי",
        contact_mobile_phone="0501234567",
    )
    session.add(company)
    await session.flush()

    # Create job
    assert company.id is not None
    job = Job(
        company_id=company.id,
        title="Python Developer",
        short_description="Short blurb for testing.",
        description="Description",
        requirements=[{"text": "Requirements"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="Tel Aviv",
        status=JobStatus.PUBLISHED,
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job)
    await session.flush()

    # Create candidate
    candidate = CandidateProfile(
        full_name="Jane Doe",
        email="jane@example.com",
        phone="050-1112233",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(job)
    await session.refresh(candidate)

    return {"job": job, "candidate": candidate}


@pytest.mark.asyncio
async def test_application_creation_sets_new_status_and_timestamps(
    session: AsyncSession, job_and_candidate
):
    """Test creating an Application (Match) model."""
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]
    assert isinstance(job, Job)
    assert isinstance(candidate, CandidateProfile)
    assert job.id is not None
    assert candidate.id is not None

    application = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)

    # Verify application was created with correct defaults
    assert application.id is not None
    assert application.job_id == job.id
    assert application.candidate_id == candidate.id
    assert application.status == ApplicationStatus.NEW
    assert application.admin_notes is None
    assert application.created_at is not None
    assert application.updated_at is not None
    assert application.resume_path is None  # new in #604, default is NULL


@pytest.mark.asyncio
async def test_application_resume_path_roundtrip(
    session: AsyncSession, job_and_candidate
):
    """Application.resume_path (per-application snapshot, #604) round-trips."""
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]
    assert isinstance(job, Job) and isinstance(candidate, CandidateProfile)
    assert job.id is not None and candidate.id is not None

    app = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
        resume_path="uploads/resumes/snapshot.pdf",
    )
    session.add(app)
    await session.commit()
    await session.refresh(app)
    assert app.resume_path == "uploads/resumes/snapshot.pdf"


@pytest.mark.asyncio
async def test_application_withdrawn_status_roundtrip(
    session: AsyncSession, job_and_candidate
):
    """ApplicationStatus.WITHDRAWN round-trips on the model + DB."""
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]
    assert isinstance(job, Job) and isinstance(candidate, CandidateProfile)
    assert job.id is not None and candidate.id is not None

    app = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
        status=ApplicationStatus.WITHDRAWN,
    )
    session.add(app)
    await session.commit()
    await session.refresh(app)
    assert app.status == ApplicationStatus.WITHDRAWN


@pytest.mark.asyncio
async def test_partial_unique_index_blocks_duplicate_active(
    session: AsyncSession, job_and_candidate
):
    """Two non-WITHDRAWN applications for the same (job, candidate) must fail."""
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]
    assert isinstance(job, Job) and isinstance(candidate, CandidateProfile)
    assert job.id is not None and candidate.id is not None

    a1 = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
        status=ApplicationStatus.NEW,
    )
    session.add(a1)
    await session.commit()

    a2 = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
        status=ApplicationStatus.NEW,
    )
    session.add(a2)
    with pytest.raises(Exception):  # IntegrityError on partial unique index
        await session.commit()


@pytest.mark.asyncio
async def test_partial_unique_index_allows_reapply_after_withdrawn(
    session: AsyncSession, job_and_candidate
):
    """A WITHDRAWN application does NOT block re-applying to the same job.

    Pins the #604-amendment behavior: the unique index is partial
    `WHERE status != 'WITHDRAWN'`, so a candidate can apply again after
    withdrawing.
    """
    job = job_and_candidate["job"]
    candidate = job_and_candidate["candidate"]
    assert isinstance(job, Job) and isinstance(candidate, CandidateProfile)
    assert job.id is not None and candidate.id is not None

    withdrawn = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
        status=ApplicationStatus.WITHDRAWN,
    )
    session.add(withdrawn)
    await session.commit()

    fresh = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
        status=ApplicationStatus.NEW,
    )
    session.add(fresh)
    await session.commit()
    await session.refresh(fresh)
    assert fresh.id is not None
    assert fresh.status == ApplicationStatus.NEW
