"""Integration tests for company job API endpoints (read and write)."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from rs_shared.enums import JobStatus
from rs_shared.models import CompanyProfile, Job
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
async def test_get_company_jobs_empty(company_client: AsyncClient):
    """Test getting jobs when none exist."""
    response = await company_client.get("/api/jobs/")
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_get_company_jobs(
    company_client: AsyncClient, company_profile: CompanyProfile
):
    """Test getting all jobs for a company."""
    # Create jobs
    async with TestSessionLocal() as session:
        assert company_profile.id is not None
        job1 = Job(
            company_id=company_profile.id,
            title="Job 1",
            short_description="Short blurb for testing.",
            description="Description 1",
            requirements=[
                {"text": "Requirements 1"},
                {"text": "Req 2"},
                {"text": "Req 3"},
            ],
            location="Location 1",
            salary_min=15000,
            salary_max=25000,
        )
        job2 = Job(
            company_id=company_profile.id,
            title="Job 2",
            short_description="Short blurb for testing.",
            description="Description 2",
            requirements=[
                {"text": "Requirements 2"},
                {"text": "Req 2"},
                {"text": "Req 3"},
            ],
            location="Location 2",
            salary_min=15000,
            salary_max=25000,
        )
        session.add(job1)
        session.add(job2)
        await session.commit()

    response = await company_client.get("/api/jobs/")
    assert response.status_code == 200

    data = response.json()["items"]
    assert len(data) == 2
    assert all("id" in job for job in data)
    assert all("title" in job for job in data)


@pytest.mark.asyncio
async def test_get_job_success(company_client: AsyncClient, pending_job: Job):
    """Test getting a specific job."""
    response = await company_client.get(f"/api/jobs/{pending_job.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == pending_job.id
    assert data["title"] == pending_job.title
    assert data["status"] == "PENDING_APPROVAL"


@pytest.mark.asyncio
async def test_get_job_not_found(company_client: AsyncClient):
    """Test getting a non-existent job."""
    response = await company_client.get("/api/jobs/999")
    assert response.status_code == 404
    assert response.json()["detail"].endswith("_not_found")


@pytest.mark.asyncio
async def test_job_read_endpoints_require_auth(unauthenticated_client: AsyncClient):
    """Job read endpoints reject requests without an auth token."""
    response = await unauthenticated_client.get("/api/jobs/")
    assert response.status_code == 401

    response = await unauthenticated_client.get("/api/jobs/1")
    assert response.status_code == 401


@pytest.mark.asyncio
@patch("rs_shared.services.company.jobs.queue_email")
@patch("rs_shared.services.company.jobs.get_all_admin_emails")
async def test_create_job_success(
    mock_get_admin_emails,
    mock_enqueue_email,
    company_client: AsyncClient,
    company_profile: CompanyProfile,
):
    """Test creating a job successfully."""
    mock_enqueue_email.return_value = "test-job-id"
    mock_get_admin_emails.return_value = ["admin@test.com"]

    job_data = {
        "title": "Senior Python Developer",
        "short_description": "Senior Python role on a small backend team.",
        "description": "We are looking for a senior Python developer...",
        "requirements": [
            {"text": "5+ years Python"},
            {"text": "FastAPI"},
            {"text": "PostgreSQL"},
        ],
        "tags": [],
        "location": "Tel Aviv, Israel",
        "salary_min": 20000,
        "salary_max": 30000,
    }

    response = await company_client.post("/api/jobs/", json=job_data)
    assert response.status_code == 201

    data = response.json()
    assert data["title"] == "Senior Python Developer"
    assert data["status"] == "PENDING_APPROVAL"
    assert data["company_id"] == company_profile.id
    assert "id" in data
    assert "created_at" in data
    assert data["salary_min"] == 20000
    assert data["salary_max"] == 30000

    # Verify email was sent
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
@patch("rs_shared.services.company.jobs.queue_email")
@patch("rs_shared.services.company.jobs.get_all_admin_emails")
async def test_update_job_success(
    mock_get_admin_emails,
    mock_enqueue_email,
    company_client: AsyncClient,
    pending_job: Job,
):
    """Test updating a job successfully."""
    mock_enqueue_email.return_value = "test-job-id"
    mock_get_admin_emails.return_value = ["admin@test.com"]

    update_data = {
        "title": "Updated Title",
        "location": "Updated Location",
    }

    response = await company_client.put(f"/api/jobs/{pending_job.id}", json=update_data)
    assert response.status_code == 200

    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["location"] == "Updated Location"
    assert data["description"] == pending_job.description  # Unchanged

    # Verify email was sent
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
async def test_update_job_not_found(company_client: AsyncClient):
    """Test updating a non-existent job."""
    update_data = {"title": "Updated Title"}

    response = await company_client.put("/api/jobs/999", json=update_data)
    assert response.status_code == 404
    assert response.json()["detail"].endswith("_not_found")


@pytest.mark.asyncio
async def test_update_job_cannot_change_status(
    company_client: AsyncClient, pending_job: Job
):
    """Test that companies cannot change job status."""
    update_data = {"status": "PUBLISHED"}

    response = await company_client.put(f"/api/jobs/{pending_job.id}", json=update_data)
    assert response.status_code == 400
    # Specific opaque code — JobCannotBeUpdatedError now maps via the
    # EXCEPTION_CODE_MAP (#648). The original "companies cannot change
    # job status" message lives in the exception args for logs only.
    assert response.json()["detail"] == "job_cannot_be_updated"


@pytest.mark.asyncio
async def test_update_job_closed_status(company_client: AsyncClient, pending_job: Job):
    """Test updating a job with CLOSED status."""
    # Set job status to CLOSED
    async with TestSessionLocal() as session:
        db_job = await session.get(Job, pending_job.id)
        if db_job is None:
            raise AssertionError(f"Job with id {pending_job.id} not found in database.")
        db_job.status = JobStatus.CLOSED
        await session.commit()

    update_data = {"title": "Updated Title"}

    response = await company_client.put(f"/api/jobs/{pending_job.id}", json=update_data)
    assert response.status_code == 400
    assert response.json()["detail"] == "job_cannot_be_updated"


@pytest.mark.asyncio
async def test_delete_job_success(company_client: AsyncClient, pending_job: Job):
    """Test deleting a job successfully."""
    job_id = pending_job.id
    response = await company_client.delete(f"/api/jobs/{job_id}")
    assert response.status_code == 204

    # Verify job was deleted
    async with TestSessionLocal() as session:
        db_job = await session.get(Job, job_id)
        assert db_job is None


@pytest.mark.asyncio
async def test_delete_job_not_found(company_client: AsyncClient):
    """Test deleting a non-existent job."""
    response = await company_client.delete("/api/jobs/999")
    assert response.status_code == 404
    assert response.json()["detail"].endswith("_not_found")


@pytest.mark.asyncio
async def test_delete_job_published_status(
    company_client: AsyncClient, pending_job: Job
):
    """Test deleting a job with PUBLISHED status."""
    # Set job status to PUBLISHED
    async with TestSessionLocal() as session:
        db_job = await session.get(Job, pending_job.id)
        if db_job is None:
            raise AssertionError(f"Job with id {pending_job.id} not found in database.")
        db_job.status = JobStatus.PUBLISHED
        await session.commit()

    response = await company_client.delete(f"/api/jobs/{pending_job.id}")
    assert response.status_code == 400
    assert response.json()["detail"] == "job_cannot_be_deleted"
    # The "only PENDING_APPROVAL jobs are deletable" rationale used to
    # leak via the detail string; it now lives only in server logs.


@pytest.mark.asyncio
async def test_job_write_endpoints_require_auth(unauthenticated_client: AsyncClient):
    """Job write endpoints reject requests without an auth token."""
    response = await unauthenticated_client.post("/api/jobs/", json={})
    assert response.status_code == 401

    response = await unauthenticated_client.put("/api/jobs/1", json={})
    assert response.status_code == 401

    response = await unauthenticated_client.delete("/api/jobs/1")
    assert response.status_code == 401


@pytest.mark.asyncio
@patch("rs_shared.services.company.jobs.queue_email")
@patch("rs_shared.services.company.jobs.get_all_admin_emails")
async def test_create_job_with_salary(
    mock_get_admin_emails,
    mock_enqueue_email,
    company_client: AsyncClient,
):
    """Salary is stored and returned when provided at creation."""
    mock_enqueue_email.return_value = "test-job-id"
    mock_get_admin_emails.return_value = []

    response = await company_client.post(
        "/api/jobs/",
        json={
            "title": "Facility Manager",
            "short_description": "Lead a small facilities team in central Tel Aviv.",
            "description": "Manage facilities.",
            "requirements": [
                {"text": "3+ years experience"},
                {"text": "Facilities leadership"},
                {"text": "Hebrew + English"},
            ],
            "tags": [],
            "location": "Tel Aviv",
            "salary_min": 15000,
            "salary_max": 20000,
        },
    )
    assert response.status_code == 201
    assert response.json()["salary_min"] == 15000
    assert response.json()["salary_max"] == 20000


@pytest.mark.asyncio
@patch("rs_shared.services.company.jobs.queue_email")
@patch("rs_shared.services.company.jobs.get_all_admin_emails")
async def test_update_job_salary(
    mock_get_admin_emails,
    mock_enqueue_email,
    company_client: AsyncClient,
    pending_job: Job,
):
    """Salary range can be updated."""
    mock_enqueue_email.return_value = "test-job-id"
    mock_get_admin_emails.return_value = []

    response = await company_client.put(
        f"/api/jobs/{pending_job.id}",
        json={"salary_min": 12000, "salary_max": 15000},
    )
    assert response.status_code == 200
    assert response.json()["salary_min"] == 12000
    assert response.json()["salary_max"] == 15000
