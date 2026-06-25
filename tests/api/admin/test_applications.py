"""Integration tests for admin application management endpoints."""

import pytest
from httpx import AsyncClient

from src.enums import ApplicationStatus
from src.models import Application, CandidateProfile, Job
from tests.conftest import TestSessionLocal

# ==================== GET /api/admin/applications ====================


@pytest.mark.asyncio
async def test_list_applications_requires_admin(public_client: AsyncClient):
    """Unauthenticated clients cannot access admin application endpoints."""
    response = await public_client.get("/api/admin/applications")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_applications_empty(admin_client: AsyncClient):
    """Returns an empty page envelope when no applications exist."""
    response = await admin_client.get("/api/admin/applications")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.asyncio
async def test_list_applications_paginates_through_all(
    admin_client: AsyncClient, published_job: Job
):
    """Cursor walk over /api/admin/applications visits every row exactly once."""
    total = 7
    async with TestSessionLocal() as session:
        for i in range(total):
            candidate = CandidateProfile(
                full_name=f"Candidate {i:02d}",
                email=f"cand{i:02d}@test.com",
                phone="050-0000000",
            )
            session.add(candidate)
            await session.flush()
            session.add(
                Application(
                    job_id=published_job.id,
                    candidate_id=candidate.id,
                    status=ApplicationStatus.NEW,
                )
            )
        await session.commit()

    seen: set[int] = set()
    cursor: str | None = None
    pages = 0
    while True:
        params: dict[str, object] = {"limit": 3}
        if cursor is not None:
            params["cursor"] = cursor
        response = await admin_client.get("/api/admin/applications", params=params)
        assert response.status_code == 200
        body = response.json()
        seen.update(item["id"] for item in body["items"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert len(seen) == total
    assert pages == 3  # 7 / 3 -> 3 pages


@pytest.mark.asyncio
async def test_list_applications_success(
    admin_client: AsyncClient,
    application: Application,
):
    """Returns applications with nested job and candidate details inside CursorPage."""
    response = await admin_client.get("/api/admin/applications")
    assert response.status_code == 200

    data = response.json()
    assert data["next_cursor"] is None
    items = data["items"]
    assert len(items) == 1
    assert items[0]["id"] == application.id
    assert items[0]["status"] == ApplicationStatus.NEW
    assert items[0]["job"] is not None
    assert items[0]["candidate"] is not None


@pytest.mark.asyncio
async def test_list_applications_filter_by_status(
    admin_client: AsyncClient,
    application: Application,
    published_job: Job,
):
    """Filter by status returns only matching applications."""
    async with TestSessionLocal() as session:
        candidate2 = CandidateProfile(
            full_name="Second Candidate",
            email="second@test.com",
            phone="050-000-0000",
        )
        session.add(candidate2)
        await session.flush()
        app2 = Application(
            job_id=published_job.id,
            candidate_id=candidate2.id,
            status=ApplicationStatus.APPROVED_BY_ADMIN,
        )
        session.add(app2)
        await session.commit()

    new_resp = await admin_client.get("/api/admin/applications?status=NEW")
    approved_resp = await admin_client.get(
        "/api/admin/applications?status=APPROVED_BY_ADMIN"
    )

    assert new_resp.status_code == 200
    assert all(a["status"] == "NEW" for a in new_resp.json()["items"])
    assert approved_resp.status_code == 200
    assert all(
        a["status"] == "APPROVED_BY_ADMIN" for a in approved_resp.json()["items"]
    )


@pytest.mark.asyncio
async def test_list_applications_filter_by_job_id(
    admin_client: AsyncClient,
    application: Application,
):
    """Filter by job_id returns only applications for that job."""
    response = await admin_client.get(
        f"/api/admin/applications?job_id={application.job_id}"
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["job_id"] == application.job_id


@pytest.mark.asyncio
async def test_list_applications_invalid_cursor_returns_400(
    admin_client: AsyncClient,
):
    response = await admin_client.get(
        "/api/admin/applications", params={"cursor": "not-a-cursor"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_applications_sort_by_name(
    admin_client: AsyncClient, published_job: Job
):
    """`sort=name&order=asc` orders by the applying candidate's full name."""
    async with TestSessionLocal() as session:
        for name in ["Bob", "Alice"]:
            candidate = CandidateProfile(
                full_name=name, email=f"{name.lower()}@test.com", phone="050-0000000"
            )
            session.add(candidate)
            await session.flush()
            session.add(
                Application(
                    job_id=published_job.id,
                    candidate_id=candidate.id,
                    status=ApplicationStatus.NEW,
                )
            )
        await session.commit()

    response = await admin_client.get(
        "/api/admin/applications", params={"sort": "name", "order": "asc"}
    )
    assert response.status_code == 200
    names = [item["candidate"]["full_name"] for item in response.json()["items"]]
    assert names == ["Alice", "Bob"]


@pytest.mark.asyncio
async def test_list_applications_invalid_sort_returns_422(admin_client: AsyncClient):
    response = await admin_client.get(
        "/api/admin/applications", params={"sort": "bogus"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_applications_sort_by_status(
    admin_client: AsyncClient, published_job: Job
):
    """`sort=status&order=asc` groups NEW applications before a terminal
    status (needs-attention first)."""
    async with TestSessionLocal() as session:
        for name, status in [
            ("Closed App", ApplicationStatus.JOB_CLOSED),
            ("New App", ApplicationStatus.NEW),
        ]:
            candidate = CandidateProfile(
                full_name=name, email=f"{name.lower()}@test.com", phone="050-0000000"
            )
            session.add(candidate)
            await session.flush()
            session.add(
                Application(
                    job_id=published_job.id, candidate_id=candidate.id, status=status
                )
            )
        await session.commit()

    response = await admin_client.get(
        "/api/admin/applications", params={"sort": "status", "order": "asc"}
    )
    assert response.status_code == 200
    statuses = [item["status"] for item in response.json()["items"]]
    assert statuses == ["NEW", "JOB_CLOSED"]


@pytest.mark.asyncio
async def test_list_applications_cross_sort_status_then_date(
    admin_client: AsyncClient, published_job: Job
):
    """`sort=status&sort2=created_at` groups by status, then orders by date
    within each group."""
    async with TestSessionLocal() as session:
        for name, status in [
            ("Older New", ApplicationStatus.NEW),
            ("Newer New", ApplicationStatus.NEW),
            ("Closed", ApplicationStatus.JOB_CLOSED),
        ]:
            slug = name.lower().replace(" ", "")
            candidate = CandidateProfile(
                full_name=name, email=f"{slug}@test.com", phone="050-0000000"
            )
            session.add(candidate)
            await session.flush()
            session.add(
                Application(
                    job_id=published_job.id, candidate_id=candidate.id, status=status
                )
            )
        await session.commit()

    response = await admin_client.get(
        "/api/admin/applications",
        params={
            "sort": "status",
            "order": "asc",
            "sort2": "created_at",
            "order2": "desc",
        },
    )
    assert response.status_code == 200
    names = [item["candidate"]["full_name"] for item in response.json()["items"]]
    assert names == ["Newer New", "Older New", "Closed"]


# ==================== GET /api/admin/applications/{id} ====================


@pytest.mark.asyncio
async def test_get_application_success(
    admin_client: AsyncClient,
    application: Application,
    candidate_profile: CandidateProfile,
):
    """Returns full application detail with nested job and candidate."""
    response = await admin_client.get(f"/api/admin/applications/{application.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == application.id
    assert data["status"] == ApplicationStatus.NEW
    assert data["job"]["id"] == application.job_id
    assert data["candidate"]["email"] == candidate_profile.email


@pytest.mark.asyncio
async def test_get_application_not_found(admin_client: AsyncClient):
    """Returns 404 for a non-existent application."""
    response = await admin_client.get("/api/admin/applications/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "application_not_found"


@pytest.mark.asyncio
async def test_get_application_requires_admin(
    public_client: AsyncClient,
    application: Application,
):
    """Unauthenticated clients cannot access application detail."""
    response = await public_client.get(f"/api/admin/applications/{application.id}")
    assert response.status_code == 401


# ==================== GET /api/admin/applications/{id}/activity ====================


@pytest.mark.asyncio
async def test_get_application_activity_returns_status_changes(
    admin_client: AsyncClient,
    application: Application,
):
    """Status updates show up newest-first on the application's activity timeline."""
    await admin_client.put(
        f"/api/admin/applications/{application.id}/status",
        json={"status": "APPROVED_BY_ADMIN"},
    )
    await admin_client.put(
        f"/api/admin/applications/{application.id}/status",
        json={"status": "HIRED"},
    )

    response = await admin_client.get(
        f"/api/admin/applications/{application.id}/activity"
    )
    assert response.status_code == 200

    items = response.json()["items"]
    assert [item["action"] for item in items] == [
        "application.status_change",
        "application.status_change",
        "application.submitted",
    ]
    assert [item["detail"] for item in items] == [
        "APPROVED_BY_ADMIN->HIRED",
        "NEW->APPROVED_BY_ADMIN",
        None,
    ]
    assert all(item["target_type"] == "Application" for item in items)


@pytest.mark.asyncio
async def test_get_application_activity_not_found(admin_client: AsyncClient):
    """Returns 404 for a non-existent application."""
    response = await admin_client.get("/api/admin/applications/99999/activity")
    assert response.status_code == 404
    assert response.json()["detail"] == "application_not_found"


@pytest.mark.asyncio
async def test_get_application_activity_requires_admin(
    public_client: AsyncClient,
    application: Application,
):
    """Unauthenticated clients cannot access the activity timeline."""
    response = await public_client.get(
        f"/api/admin/applications/{application.id}/activity"
    )
    assert response.status_code == 401


# ==================== PUT /api/admin/applications/{id}/status ====================


@pytest.mark.asyncio
async def test_update_application_status_success(
    admin_client: AsyncClient,
    application: Application,
):
    """Admin can update application status from NEW to APPROVED_BY_ADMIN."""
    response = await admin_client.put(
        f"/api/admin/applications/{application.id}/status",
        json={"status": "APPROVED_BY_ADMIN"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == application.id
    assert data["status"] == "APPROVED_BY_ADMIN"


@pytest.mark.asyncio
async def test_update_application_status_with_notes(
    admin_client: AsyncClient,
    application: Application,
):
    """Admin notes are stored alongside the status update."""
    response = await admin_client.put(
        f"/api/admin/applications/{application.id}/status",
        json={"status": "REJECTED", "admin_notes": "Not a fit for this role"},
    )
    assert response.status_code == 200
    assert response.json()["admin_notes"] == "Not a fit for this role"
    assert response.json()["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_update_application_status_skips_intermediate_steps(
    admin_client: AsyncClient,
    application: Application,
):
    """Admin can fast-forward NEW → HIRED in one step."""
    response = await admin_client.put(
        f"/api/admin/applications/{application.id}/status",
        json={"status": "HIRED"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "HIRED"


@pytest.mark.asyncio
async def test_update_application_status_not_found(admin_client: AsyncClient):
    """Returns 404 when application does not exist."""
    response = await admin_client.put(
        "/api/admin/applications/99999/status",
        json={"status": "APPROVED_BY_ADMIN"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_application_status_requires_admin(
    public_client: AsyncClient,
    application: Application,
):
    """Unauthenticated clients cannot update application status."""
    response = await public_client.put(
        f"/api/admin/applications/{application.id}/status",
        json={"status": "APPROVED_BY_ADMIN"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_application_status_missing_status(
    admin_client: AsyncClient,
    application: Application,
):
    """Returns 422 when status field is missing from the request body."""
    response = await admin_client.put(
        f"/api/admin/applications/{application.id}/status",
        json={"admin_notes": "notes only, no status"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_can_revert_terminal_status(
    admin_client: AsyncClient,
    application: Application,
):
    """Admin can revert from REJECTED back to APPROVED_BY_ADMIN — mis-click recovery."""
    await admin_client.put(
        f"/api/admin/applications/{application.id}/status",
        json={"status": "REJECTED"},
    )

    response = await admin_client.put(
        f"/api/admin/applications/{application.id}/status",
        json={"status": "APPROVED_BY_ADMIN"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED_BY_ADMIN"


# ==================== PUT /api/admin/applications/{id}/notes ====================


@pytest.mark.asyncio
async def test_update_application_notes_persists_text(
    admin_client: AsyncClient,
    application: Application,
):
    """Notes endpoint stores the text without changing status."""
    response = await admin_client.put(
        f"/api/admin/applications/{application.id}/notes",
        json={"admin_notes": "good interview"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["admin_notes"] == "good interview"
    assert data["status"] == "NEW"  # untouched


@pytest.mark.asyncio
async def test_update_application_notes_clears_to_null(
    admin_client: AsyncClient,
    application: Application,
):
    """Sending null clears the notes."""
    await admin_client.put(
        f"/api/admin/applications/{application.id}/notes",
        json={"admin_notes": "first pass"},
    )
    response = await admin_client.put(
        f"/api/admin/applications/{application.id}/notes",
        json={"admin_notes": None},
    )
    assert response.status_code == 200
    assert response.json()["admin_notes"] is None


@pytest.mark.asyncio
async def test_update_application_notes_not_found(admin_client: AsyncClient):
    response = await admin_client.put(
        "/api/admin/applications/99999/notes",
        json={"admin_notes": "x"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_application_notes_requires_admin(
    public_client: AsyncClient,
    application: Application,
):
    response = await public_client.put(
        f"/api/admin/applications/{application.id}/notes",
        json={"admin_notes": "x"},
    )
    assert response.status_code == 401


# ==================== DELETE /api/admin/applications/{id} ====================


@pytest.mark.asyncio
async def test_delete_application_success(
    admin_client: AsyncClient,
    application: Application,
):
    """Admin can delete an application; the record is removed from the DB."""
    response = await admin_client.delete(f"/api/admin/applications/{application.id}")
    assert response.status_code == 204

    # Confirm the record is gone
    get_response = await admin_client.get(f"/api/admin/applications/{application.id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_application_not_found(admin_client: AsyncClient):
    """Returns 404 when application does not exist."""
    response = await admin_client.delete("/api/admin/applications/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_application_requires_admin(
    public_client: AsyncClient,
    application: Application,
):
    """Unauthenticated clients cannot delete applications."""
    response = await public_client.delete(f"/api/admin/applications/{application.id}")
    assert response.status_code == 401


# ==================== WITHDRAWN guard ====================


@pytest.mark.asyncio
async def test_update_status_on_withdrawn_returns_409(
    admin_client: AsyncClient,
    published_job: Job,
    candidate_profile: CandidateProfile,
):
    """Admin cannot change the status of a WITHDRAWN application."""
    async with TestSessionLocal() as session:
        withdrawn_app = Application(
            job_id=published_job.id,
            candidate_id=candidate_profile.id,
            status=ApplicationStatus.WITHDRAWN,
        )
        session.add(withdrawn_app)
        await session.commit()
        await session.refresh(withdrawn_app)

    response = await admin_client.put(
        f"/api/admin/applications/{withdrawn_app.id}/status",
        json={"status": "APPROVED_BY_ADMIN"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "application_not_editable"


@pytest.mark.asyncio
async def test_update_status_on_withdrawn_does_not_change_db(
    admin_client: AsyncClient,
    published_job: Job,
    candidate_profile: CandidateProfile,
):
    """A rejected 409 must not mutate the application row."""
    async with TestSessionLocal() as session:
        withdrawn_app = Application(
            job_id=published_job.id,
            candidate_id=candidate_profile.id,
            status=ApplicationStatus.WITHDRAWN,
        )
        session.add(withdrawn_app)
        await session.commit()
        await session.refresh(withdrawn_app)

    await admin_client.put(
        f"/api/admin/applications/{withdrawn_app.id}/status",
        json={"status": "NEW"},
    )

    async with TestSessionLocal() as session:
        from sqlalchemy import select as sa_select

        refreshed = (
            await session.execute(
                sa_select(Application).where(Application.id == withdrawn_app.id)
            )
        ).scalar_one()
    assert refreshed.status == ApplicationStatus.WITHDRAWN
