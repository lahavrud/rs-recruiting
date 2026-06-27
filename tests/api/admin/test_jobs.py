"""Tests for admin job approval endpoints."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.enums import JobStatus
from src.models import CandidateProfile, CompanyProfile, Job
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
async def test_get_pending_jobs_empty(admin_client: AsyncClient):
    """Test getting pending jobs when none exist."""
    response = await admin_client.get("/api/admin/jobs/pending")
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_get_pending_jobs(
    admin_client: AsyncClient, company_profile: CompanyProfile, pending_job: Job
):
    """Test getting list of pending jobs."""
    # Create another pending job
    assert company_profile.id is not None
    async with TestSessionLocal() as session:
        job2 = Job(
            company_id=company_profile.id,
            title="Frontend Developer",
            short_description="Short blurb for testing.",
            description="We are looking for a frontend developer...",
            requirements=[
                {"text": "3+ years experience with React"},
                {"text": "Req 2"},
                {"text": "Req 3"},
            ],
            location="Remote",
            status=JobStatus.PENDING_APPROVAL,
            salary_min=15000,
            salary_max=25000,
        )
        session.add(job2)
        await session.commit()

    response = await admin_client.get("/api/admin/jobs/pending")
    assert response.status_code == 200

    data = response.json()["items"]
    assert len(data) == 2
    assert all("id" in job for job in data)
    assert all("title" in job for job in data)
    assert all(job["status"] == "PENDING_APPROVAL" for job in data)


@pytest.mark.asyncio
async def test_get_pending_jobs_excludes_published_and_closed(
    admin_client: AsyncClient, company_profile: CompanyProfile, pending_job: Job
):
    """Test that pending jobs endpoint only returns pending jobs."""
    # Create published and closed jobs
    assert company_profile.id is not None
    async with TestSessionLocal() as session:
        published_job = Job(
            company_id=company_profile.id,
            title="Published Job",
            short_description="Short blurb for testing.",
            description="This is published",
            requirements=[{"text": "N/A"}, {"text": "Req 2"}, {"text": "Req 3"}],
            location="N/A",
            status=JobStatus.PUBLISHED,
            salary_min=15000,
            salary_max=25000,
        )
        closed_job = Job(
            company_id=company_profile.id,
            title="Closed Job",
            short_description="Short blurb for testing.",
            description="This is closed",
            requirements=[{"text": "N/A"}, {"text": "Req 2"}, {"text": "Req 3"}],
            location="N/A",
            status=JobStatus.CLOSED,
            salary_min=15000,
            salary_max=25000,
        )
        session.add(published_job)
        session.add(closed_job)
        await session.commit()

    response = await admin_client.get("/api/admin/jobs/pending")
    assert response.status_code == 200

    data = response.json()["items"]
    # Should only return pending job
    assert len(data) == 1
    assert data[0]["id"] == pending_job.id
    assert data[0]["status"] == "PENDING_APPROVAL"


@pytest.mark.asyncio
@patch("src.services.admin.jobs_workflow.enqueue_email_task")
async def test_approve_job_success(
    mock_enqueue_email, admin_client: AsyncClient, pending_job: Job
):
    """Test successfully approving a job."""
    mock_enqueue_email.return_value = "test-job-id"
    response = await admin_client.post(f"/api/admin/jobs/{pending_job.id}/approve")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == pending_job.id
    assert data["status"] == "PUBLISHED"

    # Verify in database
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(Job).where(Job.id == pending_job.id)  # pyright: ignore[reportArgumentType]
        )
        job = result.scalar_one()
        assert job.status == JobStatus.PUBLISHED

    # Verify email was sent
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
async def test_approve_job_not_found(admin_client: AsyncClient):
    """Test approving a non-existent job returns 404."""
    response = await admin_client.post("/api/admin/jobs/99999/approve")
    assert response.status_code == 404
    assert response.json()["detail"].endswith("_not_found")


@pytest.mark.asyncio
async def test_approve_job_already_published(
    admin_client: AsyncClient, company_profile: CompanyProfile
):
    """Test approving an already published job returns 400."""
    # Create a published job
    assert company_profile.id is not None
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Published Job",
            short_description="Short blurb for testing.",
            description="This is published",
            requirements=[{"text": "N/A"}, {"text": "Req 2"}, {"text": "Req 3"}],
            location="N/A",
            status=JobStatus.PUBLISHED,
            salary_min=15000,
            salary_max=25000,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

    # Try to approve
    response = await admin_client.post(f"/api/admin/jobs/{job.id}/approve")
    assert response.status_code == 400
    assert response.json()["detail"].endswith("_not_pending")


@pytest.mark.asyncio
@patch("src.services.admin.jobs_workflow.enqueue_email_task")
async def test_reject_job_success(
    mock_enqueue_email, admin_client: AsyncClient, pending_job: Job
):
    """Test successfully rejecting a job."""
    mock_enqueue_email.return_value = "test-job-id"
    job_id = pending_job.id

    response = await admin_client.post(f"/api/admin/jobs/{job_id}/reject")
    assert response.status_code == 204

    # Verify job status is CLOSED
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(Job).where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
        )
        job = result.scalar_one()
        assert job.status == JobStatus.CLOSED

    # Verify email was sent
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
async def test_reject_job_not_found(admin_client: AsyncClient):
    """Test rejecting a non-existent job returns 404."""
    response = await admin_client.post("/api/admin/jobs/99999/reject")
    assert response.status_code == 404
    assert response.json()["detail"].endswith("_not_found")


@pytest.mark.asyncio
async def test_reject_job_already_published(
    admin_client: AsyncClient, company_profile: CompanyProfile
):
    """Test rejecting an already published job returns 400."""
    # Create a published job
    assert company_profile.id is not None
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Published Job",
            short_description="Short blurb for testing.",
            description="This is published",
            requirements=[{"text": "N/A"}, {"text": "Req 2"}, {"text": "Req 3"}],
            location="N/A",
            status=JobStatus.PUBLISHED,
            salary_min=15000,
            salary_max=25000,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

    # Try to reject
    response = await admin_client.post(f"/api/admin/jobs/{job.id}/reject")
    assert response.status_code == 400
    assert response.json()["detail"].endswith("_not_pending")


@pytest.mark.asyncio
@patch("src.services.admin.jobs_workflow.enqueue_email_task")
async def test_contact_job_success(
    mock_enqueue_email, admin_client: AsyncClient, pending_job: Job
):
    """Test successfully sending a contact email for a job."""
    mock_enqueue_email.return_value = "test-job-id"
    response = await admin_client.post(
        f"/api/admin/jobs/{pending_job.id}/contact",
        json={"admin_note": "נא לעדכן את דרישות המשרה."},
    )
    assert response.status_code == 204
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
@patch("src.services.admin.jobs_workflow.enqueue_email_task")
async def test_contact_job_no_note(
    mock_enqueue_email, admin_client: AsyncClient, pending_job: Job
):
    """Test contact email with empty admin note (optional field)."""
    mock_enqueue_email.return_value = "test-job-id"
    response = await admin_client.post(
        f"/api/admin/jobs/{pending_job.id}/contact",
        json={"admin_note": ""},
    )
    assert response.status_code == 204
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
@patch("src.services.admin.jobs_workflow.enqueue_email_task")
async def test_contact_job_no_body(
    mock_enqueue_email, admin_client: AsyncClient, pending_job: Job
):
    """Test contact email with no request body (admin_note defaults to empty string)."""
    mock_enqueue_email.return_value = "test-job-id"
    response = await admin_client.post(
        f"/api/admin/jobs/{pending_job.id}/contact",
        json={},
    )
    assert response.status_code == 204
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
async def test_contact_job_not_found(admin_client: AsyncClient):
    """Test contacting a non-existent job returns 404."""
    response = await admin_client.post(
        "/api/admin/jobs/99999/contact",
        json={"admin_note": "test"},
    )
    assert response.status_code == 404
    assert response.json()["detail"].endswith("_not_found")


@pytest.mark.asyncio
@patch("src.services.admin.jobs_workflow.enqueue_email_task")
async def test_contact_job_works_for_published_job(
    mock_enqueue_email, admin_client: AsyncClient, company_profile: CompanyProfile
):
    """Test contact email works for any job status (not just pending)."""
    assert company_profile.id is not None
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Published Job",
            short_description="Short blurb for testing.",
            description="Description",
            requirements=[
                {"text": "Requirements"},
                {"text": "Req 2"},
                {"text": "Req 3"},
            ],
            location="Tel Aviv",
            status=JobStatus.PUBLISHED,
            salary_min=15000,
            salary_max=25000,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

    mock_enqueue_email.return_value = "test-job-id"
    response = await admin_client.post(
        f"/api/admin/jobs/{job.id}/contact",
        json={"admin_note": "Follow-up on published job."},
    )
    assert response.status_code == 204
    mock_enqueue_email.assert_called_once()


@pytest.mark.asyncio
async def test_admin_job_endpoints_require_auth(unauthenticated_client: AsyncClient):
    """Admin job endpoints reject requests without an auth token."""
    response = await unauthenticated_client.get("/api/admin/jobs/pending")
    assert response.status_code == 401

    response = await unauthenticated_client.post("/api/admin/jobs/1/approve")
    assert response.status_code == 401

    response = await unauthenticated_client.post("/api/admin/jobs/1/reject")
    assert response.status_code == 401

    response = await unauthenticated_client.post(
        "/api/admin/jobs/1/contact", json={"admin_note": ""}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_job_endpoints_require_admin_role(
    company_role_client: AsyncClient,
):
    """Admin job endpoints reject a COMPANY-role token with 403."""
    response = await company_role_client.get("/api/admin/jobs/pending")
    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()

    response = await company_role_client.post("/api/admin/jobs/1/approve")
    assert response.status_code == 403

    response = await company_role_client.post("/api/admin/jobs/1/reject")
    assert response.status_code == 403

    response = await company_role_client.post(
        "/api/admin/jobs/1/contact", json={"admin_note": ""}
    )
    assert response.status_code == 403


def _payload(company_id: int, **overrides) -> dict:
    base = {
        "company_id": company_id,
        "title": "QA Engineer",
        "short_description": "תפקיד QA בצוות פיתוח קטן",
        "description": "ביצוע בדיקות אוטומטיות ומאניאוליות",
        "requirements": [
            {"text": "ניסיון של 2 שנים לפחות"},
            {"text": "שליטה ב-Python"},
            {"text": "היכרות עם בדיקות אוטומטיות"},
        ],
        "tags": [],
        "location": "רמת גן",
        "salary_min": 14000,
        "salary_max": 20000,
    }
    base.update(overrides)
    return base


# ── POST /api/admin/jobs ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_job_defaults_to_published(
    admin_client: AsyncClient, company_profile: CompanyProfile
):
    response = await admin_client.post(
        "/api/admin/jobs", json=_payload(company_profile.id)
    )
    assert response.status_code == 201
    data = response.json()
    assert data["company_id"] == company_profile.id
    assert data["status"] == JobStatus.PUBLISHED.value
    assert data["title"] == "QA Engineer"


@pytest.mark.asyncio
async def test_create_job_with_explicit_status(
    admin_client: AsyncClient, company_profile: CompanyProfile
):
    response = await admin_client.post(
        "/api/admin/jobs",
        json=_payload(company_profile.id, status=JobStatus.PENDING_APPROVAL.value),
    )
    assert response.status_code == 201
    assert response.json()["status"] == JobStatus.PENDING_APPROVAL.value


@pytest.mark.asyncio
async def test_create_job_unknown_company_returns_404(admin_client: AsyncClient):
    response = await admin_client.post(
        "/api/admin/jobs", json=_payload(company_id=99999)
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_job_requires_admin(public_client: AsyncClient):
    response = await public_client.post("/api/admin/jobs", json=_payload(1))
    assert response.status_code == 401


# ── GET /api/admin/jobs/{id} ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_job_returns_any_status(admin_client: AsyncClient, pending_job: Job):
    response = await admin_client.get(f"/api/admin/jobs/{pending_job.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == pending_job.id
    assert data["status"] == JobStatus.PENDING_APPROVAL.value


@pytest.mark.asyncio
async def test_get_job_not_found(admin_client: AsyncClient):
    response = await admin_client.get("/api/admin/jobs/99999")
    assert response.status_code == 404


# ── PUT /api/admin/jobs/{id} ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_job_partial(admin_client: AsyncClient, pending_job: Job):
    response = await admin_client.put(
        f"/api/admin/jobs/{pending_job.id}",
        json={"title": "Updated Title", "status": JobStatus.PUBLISHED.value},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["status"] == JobStatus.PUBLISHED.value
    # Untouched fields preserved
    assert data["description"] == pending_job.description


@pytest.mark.asyncio
async def test_update_job_not_found(admin_client: AsyncClient):
    response = await admin_client.put("/api/admin/jobs/99999", json={"title": "x"})
    assert response.status_code == 404


# ── DELETE /api/admin/jobs/{id} ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_job_succeeds(admin_client: AsyncClient, pending_job: Job):
    response = await admin_client.delete(f"/api/admin/jobs/{pending_job.id}")
    assert response.status_code == 204

    # Subsequent GET returns 404
    follow_up = await admin_client.get(f"/api/admin/jobs/{pending_job.id}")
    assert follow_up.status_code == 404


@pytest.mark.asyncio
async def test_delete_job_not_found(admin_client: AsyncClient):
    response = await admin_client.delete("/api/admin/jobs/99999")
    assert response.status_code == 404


# ── GET /api/admin/jobs (list-all-statuses, paginated) ───────────────────────


@pytest.mark.asyncio
async def test_list_jobs_envelope(admin_client: AsyncClient, pending_job: Job):
    response = await admin_client.get("/api/admin/jobs")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "next_cursor"}
    assert any(item["id"] == pending_job.id for item in body["items"])


@pytest.mark.asyncio
async def test_list_jobs_filters_by_status(
    admin_client: AsyncClient, pending_job: Job, published_job: Job
):
    response = await admin_client.get(
        "/api/admin/jobs", params={"status": JobStatus.PUBLISHED.value}
    )
    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert published_job.id in ids
    assert pending_job.id not in ids


@pytest.mark.asyncio
async def test_list_jobs_invalid_cursor_returns_400(admin_client: AsyncClient):
    response = await admin_client.get(
        "/api/admin/jobs", params={"cursor": "not-a-cursor"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_jobs_paginates_through_all(
    admin_client: AsyncClient,
    company_profile: CompanyProfile,
):
    """Cursor walk over /api/admin/jobs visits every job exactly once."""
    total = 7
    for i in range(total):
        response = await admin_client.post(
            "/api/admin/jobs",
            json=_payload(company_profile.id, title=f"Role {i:02d}"),
        )
        assert response.status_code == 201

    seen: set[int] = set()
    cursor: str | None = None
    pages = 0
    while True:
        params: dict[str, object] = {"limit": 3}
        if cursor is not None:
            params["cursor"] = cursor
        response = await admin_client.get("/api/admin/jobs", params=params)
        assert response.status_code == 200
        body = response.json()
        seen.update(item["id"] for item in body["items"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert len(seen) == total
    assert pages == 3


@pytest.mark.asyncio
async def test_list_jobs_requires_admin(public_client: AsyncClient):
    response = await public_client.get("/api/admin/jobs")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_jobs_sort_by_name(
    admin_client: AsyncClient, company_profile: CompanyProfile
):
    for title in ["Charlie Role", "Alpha Role"]:
        response = await admin_client.post(
            "/api/admin/jobs", json=_payload(company_profile.id, title=title)
        )
        assert response.status_code == 201

    response = await admin_client.get(
        "/api/admin/jobs", params={"sort": "name", "order": "asc"}
    )
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert titles == ["Alpha Role", "Charlie Role"]


@pytest.mark.asyncio
async def test_list_jobs_invalid_sort_returns_422(admin_client: AsyncClient):
    response = await admin_client.get(
        "/api/admin/jobs", params={"sort": "not_a_column"}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/admin/jobs/{id}/candidate-matches
# ---------------------------------------------------------------------------


async def _make_candidate(full_name: str, email: str, embedding: list[float]) -> int:
    async with TestSessionLocal() as s:
        candidate = CandidateProfile(
            full_name=full_name,
            email=email,
            phone="050-0000000",
            embedding=embedding,
        )
        s.add(candidate)
        await s.commit()
        await s.refresh(candidate)
        return candidate.id


@pytest.mark.asyncio
async def test_get_job_candidate_matches_ranked(
    admin_client: AsyncClient,
    published_job: Job,
    fake_embeddings,
):
    """Ranks every embedded candidate against the job, best score first."""
    [job_vec] = await fake_embeddings.embed(["python fastapi backend"])
    async with TestSessionLocal() as s:
        job = await s.get(Job, published_job.id)
        job.embedding = job_vec
        await s.commit()

    [close_vec] = await fake_embeddings.embed(["python fastapi backend developer"])
    [far_vec] = await fake_embeddings.embed(["marketing brand social media"])
    close_id = await _make_candidate("Close Match", "close@test.com", close_vec)
    far_id = await _make_candidate("Far Match", "far@test.com", far_vec)

    resp = await admin_client.get(
        f"/api/admin/jobs/{published_job.id}/candidate-matches"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert [m["candidate"]["id"] for m in data] == [close_id, far_id]
    assert data[0]["score"] > data[1]["score"]


@pytest.mark.asyncio
async def test_get_job_candidate_matches_excludes_unembedded_candidates(
    admin_client: AsyncClient,
    published_job: Job,
    fake_embeddings,
):
    """A candidate with no resume/embedding never shows up in the ranking."""
    [job_vec] = await fake_embeddings.embed(["python fastapi backend"])
    async with TestSessionLocal() as s:
        job = await s.get(Job, published_job.id)
        job.embedding = job_vec
        await s.commit()
        s.add(
            CandidateProfile(
                full_name="No Resume", email="noresume@test.com", phone="050-0000000"
            )
        )
        await s.commit()

    resp = await admin_client.get(
        f"/api/admin/jobs/{published_job.id}/candidate-matches"
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_job_candidate_matches_empty_when_job_not_embedded(
    admin_client: AsyncClient, pending_job: Job
):
    """A job with no embedding yet (e.g. not published) returns no matches."""
    resp = await admin_client.get(f"/api/admin/jobs/{pending_job.id}/candidate-matches")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_job_candidate_matches_empty_when_job_closed(
    admin_client: AsyncClient,
    published_job: Job,
    fake_embeddings,
):
    """A closed job keeps a stale embedding but must stop returning matches."""
    [job_vec] = await fake_embeddings.embed(["python fastapi backend"])
    [cand_vec] = await fake_embeddings.embed(["python fastapi backend developer"])
    async with TestSessionLocal() as s:
        job = await s.get(Job, published_job.id)
        job.embedding = job_vec
        job.status = JobStatus.CLOSED
        await s.commit()
    await _make_candidate("Closed Job Match", "closedjob@test.com", cand_vec)

    resp = await admin_client.get(
        f"/api/admin/jobs/{published_job.id}/candidate-matches"
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_job_candidate_matches_404_for_unknown_job(
    admin_client: AsyncClient,
):
    resp = await admin_client.get("/api/admin/jobs/999999/candidate-matches")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_job_candidate_matches_requires_admin(public_client: AsyncClient):
    resp = await public_client.get("/api/admin/jobs/1/candidate-matches")
    assert resp.status_code in (401, 403)
