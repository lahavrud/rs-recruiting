"""Integration tests for admin candidate management endpoints."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AuditLog, CandidateProfile


@pytest.mark.asyncio
async def test_list_candidates_empty(admin_client: AsyncClient):
    """Returns an empty page when no candidates exist."""
    response = await admin_client.get("/api/admin/candidates")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.asyncio
async def test_list_candidates_success(
    admin_client: AsyncClient,
    candidate_profile: CandidateProfile,
):
    """Returns the candidate inside a CursorPage envelope."""
    response = await admin_client.get("/api/admin/candidates")
    assert response.status_code == 200

    data = response.json()
    assert data["next_cursor"] is None
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == candidate_profile.id
    assert data["items"][0]["full_name"] == candidate_profile.full_name
    assert data["items"][0]["email"] == candidate_profile.email


@pytest.mark.asyncio
async def test_list_candidates_requires_admin(public_client: AsyncClient):
    """Unauthenticated clients cannot access the candidates list."""
    response = await public_client.get("/api/admin/candidates")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_candidates_filters_by_q(
    admin_client: AsyncClient,
    candidate_profile: CandidateProfile,
):
    """`q` filters by name/email/phone, case-insensitively."""
    response = await admin_client.get(
        "/api/admin/candidates",
        params={"q": candidate_profile.full_name.upper()[:4]},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == candidate_profile.id

    no_match = await admin_client.get(
        "/api/admin/candidates", params={"q": "zzz-no-such-candidate"}
    )
    assert no_match.status_code == 200
    assert no_match.json()["items"] == []


@pytest.mark.asyncio
async def test_list_candidates_invalid_cursor_returns_400(admin_client: AsyncClient):
    """Garbage cursors return 400 instead of leaking a stack trace."""
    response = await admin_client.get(
        "/api/admin/candidates", params={"cursor": "not-a-real-cursor"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_candidates_sort_by_name(
    admin_client: AsyncClient, session: AsyncSession
):
    """`sort=name&order=asc` orders the response alphabetically."""
    session.add_all(
        [
            CandidateProfile(
                full_name="Bob", email="bob@test.com", phone="050-2222222"
            ),
            CandidateProfile(
                full_name="Alice", email="alice@test.com", phone="050-1111111"
            ),
        ]
    )
    await session.commit()

    response = await admin_client.get(
        "/api/admin/candidates", params={"sort": "name", "order": "asc"}
    )
    assert response.status_code == 200
    names = [item["full_name"] for item in response.json()["items"]]
    assert names == ["Alice", "Bob"]


@pytest.mark.asyncio
async def test_list_candidates_invalid_sort_returns_422(admin_client: AsyncClient):
    response = await admin_client.get("/api/admin/candidates", params={"sort": "email"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_candidates_cursor_rejects_sort_change_returns_400(
    admin_client: AsyncClient, session: AsyncSession
):
    """Changing `sort` with a stale cursor is rejected, not silently misordered."""
    session.add_all(
        [
            CandidateProfile(
                full_name=f"User{i:02d}",
                email=f"user{i:02d}@test.com",
                phone="050-0000000",
            )
            for i in range(15)
        ]
    )
    await session.commit()

    first = await admin_client.get(
        "/api/admin/candidates", params={"limit": 10, "sort": "created_at"}
    )
    cursor = first.json()["next_cursor"]
    assert cursor is not None

    response = await admin_client.get(
        "/api/admin/candidates",
        params={"cursor": cursor, "sort": "name"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_candidates_paginates_through_all(
    admin_client: AsyncClient, session: AsyncSession
):
    """Page-by-page traversal covers every candidate exactly once."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(25):
        session.add(
            CandidateProfile(
                full_name=f"User {i:02d}",
                email=f"user{i:02d}@test.com",
                phone="050-0000000",
                created_at=base + timedelta(minutes=i),
            )
        )
    await session.commit()

    seen: list[str] = []
    cursor: str | None = None
    while True:
        params: dict[str, str | int] = {"limit": 10}
        if cursor is not None:
            params["cursor"] = cursor
        response = await admin_client.get("/api/admin/candidates", params=params)
        assert response.status_code == 200
        data = response.json()
        seen.extend(item["email"] for item in data["items"])
        if data["next_cursor"] is None:
            break
        cursor = data["next_cursor"]

    assert len(seen) == 25
    assert seen[0] == "user24@test.com"
    assert seen[-1] == "user00@test.com"


# ── GET /api/admin/candidates/{id} ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_candidate_returns_profile(
    admin_client: AsyncClient, candidate_profile: CandidateProfile
):
    response = await admin_client.get(f"/api/admin/candidates/{candidate_profile.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == candidate_profile.id
    assert data["email"] == candidate_profile.email


@pytest.mark.asyncio
async def test_get_candidate_not_found(admin_client: AsyncClient):
    response = await admin_client.get("/api/admin/candidates/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_candidate_requires_admin(
    public_client: AsyncClient, candidate_profile: CandidateProfile
):
    response = await public_client.get(f"/api/admin/candidates/{candidate_profile.id}")
    assert response.status_code == 401


# ── GET /api/admin/candidates/{id}/activity ───────────────────────────────────


@pytest.mark.asyncio
async def test_get_candidate_activity_empty(
    admin_client: AsyncClient, candidate_profile: CandidateProfile
):
    response = await admin_client.get(
        f"/api/admin/candidates/{candidate_profile.id}/activity"
    )
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.asyncio
async def test_get_candidate_activity_merges_application_events(
    admin_client: AsyncClient,
    candidate_profile: CandidateProfile,
    application,
    session: AsyncSession,
):
    session.add(
        AuditLog(
            action="candidate.consent",
            target_type="CandidateProfile",
            target_id=candidate_profile.id,
        )
    )
    session.add(
        AuditLog(
            action="application.status_change",
            target_type="Application",
            target_id=application.id,
            detail="NEW->APPROVED_BY_ADMIN",
        )
    )
    await session.commit()

    response = await admin_client.get(
        f"/api/admin/candidates/{candidate_profile.id}/activity"
    )
    assert response.status_code == 200
    items = response.json()["items"]
    actions = {item["action"] for item in items}
    assert actions == {"candidate.consent", "application.status_change"}
    status_change = next(i for i in items if i["action"] == "application.status_change")
    assert status_change["job_title"] == "Senior Python Developer"
    consent = next(i for i in items if i["action"] == "candidate.consent")
    assert consent["job_title"] is None


@pytest.mark.asyncio
async def test_get_candidate_activity_not_found(admin_client: AsyncClient):
    response = await admin_client.get("/api/admin/candidates/99999/activity")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_candidate_activity_requires_admin(
    public_client: AsyncClient, candidate_profile: CandidateProfile
):
    response = await public_client.get(
        f"/api/admin/candidates/{candidate_profile.id}/activity"
    )
    assert response.status_code == 401


# ── DELETE /api/admin/candidates/{id} ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_candidate_succeeds(
    admin_client: AsyncClient, candidate_profile: CandidateProfile
):
    response = await admin_client.delete(
        f"/api/admin/candidates/{candidate_profile.id}"
    )
    assert response.status_code == 204

    follow_up = await admin_client.get(f"/api/admin/candidates/{candidate_profile.id}")
    assert follow_up.status_code == 404


@pytest.mark.asyncio
async def test_delete_candidate_removes_resume_from_storage(
    admin_client: AsyncClient, session: AsyncSession
):
    """Deleting a candidate via the API triggers storage cleanup for their resume."""
    candidate = CandidateProfile(
        full_name="Resume Owner",
        email="resowner@test.com",
        phone="050-1234567",
        resume_path="resumes/abc-uuid.pdf",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    with patch("src.services.admin.candidates.get_storage_provider") as storage_factory:
        delete_mock = AsyncMock(return_value=True)
        storage_factory.return_value.delete_file = delete_mock

        response = await admin_client.delete(f"/api/admin/candidates/{candidate.id}")

    assert response.status_code == 204
    delete_mock.assert_awaited_once_with("resumes/abc-uuid.pdf")


@pytest.mark.asyncio
async def test_delete_candidate_not_found(admin_client: AsyncClient):
    response = await admin_client.delete("/api/admin/candidates/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_candidate_endpoints_require_admin(
    public_client: AsyncClient, candidate_profile: CandidateProfile
):
    delete_resp = await public_client.delete(
        f"/api/admin/candidates/{candidate_profile.id}"
    )
    assert delete_resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/admin/candidates/{id}/job-matches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_candidate_job_matches_ranked(
    admin_client: AsyncClient,
    company_profile,
    candidate_profile: CandidateProfile,
    fake_embeddings,
):
    """Ranks every PUBLISHED, embedded job against the candidate, best score first."""
    from src.enums import JobStatus
    from src.models import Job
    from tests.conftest import TestSessionLocal

    [cand_vec] = await fake_embeddings.embed(["python fastapi backend developer"])
    async with TestSessionLocal() as s:
        candidate = await s.get(CandidateProfile, candidate_profile.id)
        candidate.embedding = cand_vec
        await s.commit()

    [close_vec] = await fake_embeddings.embed(["python fastapi backend"])
    [far_vec] = await fake_embeddings.embed(["marketing brand social media"])
    async with TestSessionLocal() as s:
        low = Job(
            company_id=company_profile.id,
            title="Lower Match",
            short_description="x",
            description="y",
            requirements=[{"text": "a"}, {"text": "b"}, {"text": "c"}],
            tags=[],
            location="Tel Aviv",
            salary_min=1,
            salary_max=2,
            status=JobStatus.PUBLISHED,
            embedding=far_vec,
        )
        high = Job(
            company_id=company_profile.id,
            title="Higher Match",
            short_description="x",
            description="y",
            requirements=[{"text": "a"}, {"text": "b"}, {"text": "c"}],
            tags=[],
            location="Haifa",
            salary_min=1,
            salary_max=2,
            status=JobStatus.PUBLISHED,
            embedding=close_vec,
        )
        s.add_all([low, high])
        await s.commit()
        await s.refresh(low)
        await s.refresh(high)
        high_id, low_id = high.id, low.id

    resp = await admin_client.get(
        f"/api/admin/candidates/{candidate_profile.id}/job-matches"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert [m["job"]["id"] for m in data] == [high_id, low_id]
    assert data[0]["job"]["title"] == "Higher Match"
    assert data[0]["score"] > data[1]["score"]


@pytest.mark.asyncio
async def test_get_candidate_job_matches_excludes_closed_job(
    admin_client: AsyncClient,
    company_profile,
    candidate_profile: CandidateProfile,
    fake_embeddings,
):
    """A closed job must drop out of the live ranking even if still embedded."""
    from src.enums import JobStatus
    from src.models import Job
    from tests.conftest import TestSessionLocal

    [vec] = await fake_embeddings.embed(["python fastapi backend"])
    async with TestSessionLocal() as s:
        candidate = await s.get(CandidateProfile, candidate_profile.id)
        candidate.embedding = vec
        await s.commit()

        open_job = Job(
            company_id=company_profile.id,
            title="Still Open",
            short_description="x",
            description="y",
            requirements=[{"text": "a"}, {"text": "b"}, {"text": "c"}],
            tags=[],
            location="Tel Aviv",
            salary_min=1,
            salary_max=2,
            status=JobStatus.PUBLISHED,
            embedding=vec,
        )
        closed_job = Job(
            company_id=company_profile.id,
            title="Closed Role",
            short_description="x",
            description="y",
            requirements=[{"text": "a"}, {"text": "b"}, {"text": "c"}],
            tags=[],
            location="Haifa",
            salary_min=1,
            salary_max=2,
            status=JobStatus.CLOSED,
            embedding=vec,
        )
        s.add_all([open_job, closed_job])
        await s.commit()
        await s.refresh(open_job)
        open_id = open_job.id

    resp = await admin_client.get(
        f"/api/admin/candidates/{candidate_profile.id}/job-matches"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert [m["job"]["id"] for m in data] == [open_id]


@pytest.mark.asyncio
async def test_get_candidate_job_matches_empty_when_none(
    admin_client: AsyncClient,
    candidate_profile: CandidateProfile,
):
    resp = await admin_client.get(
        f"/api/admin/candidates/{candidate_profile.id}/job-matches"
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_candidate_job_matches_404_for_unknown_candidate(
    admin_client: AsyncClient,
):
    resp = await admin_client.get("/api/admin/candidates/999999/job-matches")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_candidate_job_matches_requires_admin(public_client: AsyncClient):
    resp = await public_client.get("/api/admin/candidates/1/job-matches")
    assert resp.status_code in (401, 403)
