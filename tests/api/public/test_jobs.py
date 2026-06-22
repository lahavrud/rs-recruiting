"""Integration tests for public API endpoints (no authentication required)."""

import pytest
from httpx import AsyncClient

from src.enums import JobStatus
from src.models import CompanyProfile, Job
from src.schemas import JobPublicRead
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
async def test_get_public_jobs_empty(public_client: AsyncClient):
    """Test getting public jobs when none exist."""
    response = await public_client.get("/api/public/jobs")
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_get_public_jobs_only_published(
    public_client: AsyncClient,
    company_profile: CompanyProfile,
    published_job: Job,
    pending_job: Job,
    closed_job: Job,
):
    """Test that public endpoint only returns published jobs."""
    response = await public_client.get("/api/public/jobs")
    assert response.status_code == 200

    data = response.json()["items"]
    # Should only return published job, not pending or closed
    assert len(data) == 1
    assert data[0]["id"] == published_job.id
    assert data[0]["title"] == "Senior Python Developer"
    assert "status" not in data[0]


@pytest.mark.asyncio
async def test_get_public_jobs_multiple_published(
    public_client: AsyncClient, company_profile: CompanyProfile, published_job: Job
):
    """Test getting multiple published jobs."""
    # Create another published job
    async with TestSessionLocal() as session:
        job2 = Job(
            company_id=company_profile.id if company_profile.id is not None else 0,
            title="Frontend Developer",
            short_description="Short blurb for testing.",
            description="We are looking for a frontend developer...",
            requirements=[
                {"text": "3+ years experience with React"},
                {"text": "Req 2"},
                {"text": "Req 3"},
            ],
            location="Tel Aviv, Israel",
            status=JobStatus.PUBLISHED,
            salary_min=15000,
            salary_max=25000,
        )
        session.add(job2)
        await session.commit()

    response = await public_client.get("/api/public/jobs")
    assert response.status_code == 200

    data = response.json()["items"]
    assert len(data) == 2
    # Should be ordered by creation date (newest first)
    assert all("id" in job for job in data)
    assert all("title" in job for job in data)
    assert all("status" not in job for job in data)


@pytest.mark.asyncio
async def test_get_public_job_success(public_client: AsyncClient, published_job: Job):
    """Test getting a specific published job."""
    response = await public_client.get(f"/api/public/jobs/{published_job.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == published_job.id
    assert data["title"] == published_job.title
    assert data["description"] == published_job.description
    assert data["requirements"] == published_job.requirements
    assert data["location"] == published_job.location
    assert "salary_min" in data
    assert "salary_max" in data
    assert "status" not in data


@pytest.mark.asyncio
async def test_get_public_job_not_found(public_client: AsyncClient):
    """Test getting a non-existent job returns 404."""
    response = await public_client.get("/api/public/jobs/99999")
    assert response.status_code == 404
    assert response.json()["detail"].endswith("_not_found")


@pytest.mark.asyncio
async def test_get_public_job_pending_not_visible(
    public_client: AsyncClient, pending_job: Job
):
    """Test that pending jobs are not visible via public endpoint."""
    response = await public_client.get(f"/api/public/jobs/{pending_job.id}")
    assert response.status_code == 404
    # Pending + closed + truly-missing all collapse into the same opaque
    # "job_not_found" so callers can't probe lifecycle state.
    assert response.json()["detail"] == "job_not_found"


@pytest.mark.asyncio
async def test_get_public_job_closed_not_visible(
    public_client: AsyncClient, closed_job: Job
):
    """Test that closed jobs are not visible via public endpoint."""
    response = await public_client.get(f"/api/public/jobs/{closed_job.id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "job_not_found"


@pytest.mark.asyncio
async def test_get_public_job_omits_internal_fields(
    public_client: AsyncClient, published_job: Job
):
    """Test that internal fields are omitted from public job responses."""
    response = await public_client.get(f"/api/public/jobs/{published_job.id}")
    assert response.status_code == 200

    # Extract job data
    data = response.json()

    # 1. Dynamically derive public fields from the schema
    public_fields = set(JobPublicRead.model_fields.keys())

    # 2. Check the raw response for internal fields
    unexpected_keys = set(data.keys()) - public_fields

    assert not unexpected_keys, f"Unexpected fields in response: {unexpected_keys}"

    # 3. Ensure that all public fields are included
    assert public_fields.issubset(data.keys()), "Missing expected public fields."


@pytest.mark.asyncio
async def test_public_endpoints_no_auth_required(
    public_client: AsyncClient, published_job: Job
):
    """Test that public endpoints work without authentication."""
    # These endpoints should work without any auth token
    response = await public_client.get("/api/public/jobs")
    assert response.status_code == 200
    list_data = response.json()
    assert "items" in list_data
    assert list_data["items"][0]["id"] == published_job.id
    assert list_data["items"][0]["title"] == published_job.title

    response = await public_client.get(f"/api/public/jobs/{published_job.id}")
    assert response.status_code == 200
    detail_data = response.json()
    assert detail_data["id"] == published_job.id
    assert detail_data["title"] == published_job.title


@pytest.mark.asyncio
async def test_get_public_job_payload_integrity(
    public_client: AsyncClient, published_job: Job
):
    """Verify that the public API response matches the JobPublicRead schema exactly."""
    response = await public_client.get(f"/api/public/jobs/{published_job.id}")
    assert response.status_code == 200

    data = response.json()

    # 1. Validate the structure matches the schema
    # This ensures required fields (title, etc.) are present and valid
    job_public = JobPublicRead.model_validate(data)

    # 2. Check the raw JSON keys to ensure no internal data leaked
    # hasattr(job_public, ...) only checks the Python class, not the actual API output
    assert "company_id" not in data
    assert "updated_at" not in data

    # 3. Verify specific values
    assert job_public.id == published_job.id
    assert job_public.title == published_job.title

    # 4. Assert that only the allowed keys exist in the response.
    # `my_application` is part of the schema (added in #606) but only
    # populated for authenticated candidate sessions; anonymous responses
    # serialize it as `null`.
    expected_keys = {
        "id",
        "title",
        "short_description",
        "description",
        "requirements",
        "tags",
        "is_featured",
        "location",
        "salary_min",
        "salary_max",
        "created_at",
        "my_application",
    }
    assert set(data.keys()) == expected_keys
    assert data["my_application"] is None


# ── Sprint 11 / #606 — my_application surfacing ───────────────────────────────


@pytest.mark.asyncio
async def test_get_public_job_my_application_for_candidate_with_new_app(
    public_client: AsyncClient, published_job: Job, test_db
):
    """Authed candidate with a NEW application sees `my_application.editable=true`."""
    from src.core.infrastructure.security import create_access_token, get_password_hash
    from src.enums import ApplicationStatus, UserRole
    from src.models import Application, CandidateProfile, User

    async with TestSessionLocal() as session:
        user = User(
            email="me@example.com",
            hashed_password=get_password_hash("Secret1!"),  # pragma: allowlist secret
            role=UserRole.CANDIDATE,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        profile = CandidateProfile(
            user_id=user.id,
            full_name="Me",
            email="me@example.com",
            phone="050-000-0001",
        )
        session.add(profile)
        await session.flush()
        app = Application(
            job_id=published_job.id,
            candidate_id=profile.id,
            status=ApplicationStatus.NEW,
        )
        session.add(app)
        await session.commit()
        await session.refresh(app)
        token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value,
            }
        )
        app_id = app.id

    resp = await public_client.get(
        f"/api/public/jobs/{published_job.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    my = resp.json()["my_application"]
    assert my is not None
    assert my["id"] == app_id
    assert my["editable"] is True


@pytest.mark.asyncio
async def test_get_public_job_my_application_for_candidate_with_locked_app(
    public_client: AsyncClient, published_job: Job, test_db
):
    """Authed candidate whose application is past NEW sees `editable=false`."""
    from src.core.infrastructure.security import create_access_token, get_password_hash
    from src.enums import ApplicationStatus, UserRole
    from src.models import Application, CandidateProfile, User

    async with TestSessionLocal() as session:
        user = User(
            email="locked@example.com",
            hashed_password=get_password_hash("Secret1!"),  # pragma: allowlist secret
            role=UserRole.CANDIDATE,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        profile = CandidateProfile(
            user_id=user.id,
            full_name="Locked",
            email="locked@example.com",
            phone="050-000-0002",
        )
        session.add(profile)
        await session.flush()
        session.add(
            Application(
                job_id=published_job.id,
                candidate_id=profile.id,
                status=ApplicationStatus.APPROVED_BY_ADMIN,
            )
        )
        await session.commit()
        token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value,
            }
        )

    resp = await public_client.get(
        f"/api/public/jobs/{published_job.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    my = resp.json()["my_application"]
    assert my is not None
    assert my["editable"] is False


@pytest.mark.asyncio
async def test_get_public_job_my_application_withdrawn_is_hidden(
    public_client: AsyncClient, published_job: Job, test_db
):
    """Withdrawn applications are invisible — `my_application` is null."""
    from src.core.infrastructure.security import create_access_token, get_password_hash
    from src.enums import ApplicationStatus, UserRole
    from src.models import Application, CandidateProfile, User

    async with TestSessionLocal() as session:
        user = User(
            email="withdrawn@example.com",
            hashed_password=get_password_hash("Secret1!"),  # pragma: allowlist secret
            role=UserRole.CANDIDATE,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        profile = CandidateProfile(
            user_id=user.id,
            full_name="Withdrawn",
            email="withdrawn@example.com",
            phone="050-000-0003",
        )
        session.add(profile)
        await session.flush()
        session.add(
            Application(
                job_id=published_job.id,
                candidate_id=profile.id,
                status=ApplicationStatus.WITHDRAWN,
            )
        )
        await session.commit()
        token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value,
            }
        )

    resp = await public_client.get(
        f"/api/public/jobs/{published_job.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["my_application"] is None
