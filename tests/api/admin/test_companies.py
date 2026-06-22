"""Tests for admin company approval endpoints."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models import CompanyProfile, User
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.auth.registration import (
    CompanyRegistrationData,
    register_company_user,
)
from tests.conftest import FAKE_LOGO, FAKE_SIG_B64, TestSessionLocal


@pytest.mark.asyncio
async def test_get_pending_companies_empty(admin_client: AsyncClient):
    """Returns an empty page envelope when no pending companies exist."""
    response = await admin_client.get("/api/admin/companies/pending")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.asyncio
@patch("src.services.auth.registration.enqueue_email_task")
async def test_get_pending_companies(
    mock_enqueue_email, admin_client: AsyncClient, company_user
):
    """Returns pending companies inside a CursorPage envelope."""
    mock_enqueue_email.return_value = "test-job-id"
    # Create another pending company
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="company2@test.com",
            password="SecurePass1!",
            company_profile=CompanyProfileCreate(
                name="Company 2",
                company_id="123456789",
                address="רח׳ הדוגמה 1, תל אביב",
                contact_first_name="ישראל",
                contact_last_name="ישראלי",
                contact_mobile_phone="0501234567",
            ),
        )
        await register_company_user(
            user_data,
            session,
            FAKE_LOGO,
            "logo.png",
            CompanyRegistrationData(
                logo_content_type="image/png", agreement_signature=FAKE_SIG_B64
            ),
        )
        await session.commit()

    response = await admin_client.get("/api/admin/companies/pending")
    assert response.status_code == 200

    data = response.json()
    assert data["next_cursor"] is None
    assert len(data["items"]) == 2

    for company in data["items"]:
        assert "user" in company
        assert "company_profile" in company
        assert company["user"]["is_active"] is False
        assert company["user"]["role"] == "COMPANY"


@pytest.mark.asyncio
async def test_pending_companies_invalid_cursor_returns_400(
    admin_client: AsyncClient,
):
    response = await admin_client.get(
        "/api/admin/companies/pending", params={"cursor": "not-a-cursor"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_active_companies_invalid_cursor_returns_400(
    admin_client: AsyncClient,
):
    response = await admin_client.get(
        "/api/admin/companies", params={"cursor": "not-a-cursor"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_active_companies_empty_envelope(admin_client: AsyncClient):
    response = await admin_client.get("/api/admin/companies")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.asyncio
@patch("src.services.admin.company_approval.enqueue_email_task")
async def test_approve_company_success(
    mock_enqueue_email, admin_client: AsyncClient, company_user
):
    """Test successfully approving a company."""
    mock_enqueue_email.return_value = "test-job-id"
    response = await admin_client.post(
        f"/api/admin/companies/{company_user.id}/approve"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["user"]["id"] == company_user.id
    # Approval creates an ActivationToken but does NOT set is_active=True yet
    assert data["user"]["is_active"] is False
    assert data["company_profile"]["name"] == "Test Company"

    # Verify in database — still inactive until company clicks the link
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == company_user.id)  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        assert user.is_active is False


@pytest.mark.asyncio
async def test_approve_company_not_found(admin_client: AsyncClient):
    """Test approving a non-existent company returns 404."""
    response = await admin_client.post("/api/admin/companies/99999/approve")
    assert response.status_code == 404
    assert response.json()["detail"].endswith("_not_found")


@pytest.mark.asyncio
@patch("src.services.admin.company_approval.enqueue_email_task")
async def test_approve_company_already_approved(
    mock_enqueue_email, admin_client: AsyncClient, company_user
):
    """Test re-approving revokes the previous token and issues a fresh one (200)."""
    mock_enqueue_email.return_value = "test-job-id"
    response1 = await admin_client.post(
        f"/api/admin/companies/{company_user.id}/approve"
    )
    assert response1.status_code == 200

    # Second approve revokes old token and sends a fresh activation email
    response2 = await admin_client.post(
        f"/api/admin/companies/{company_user.id}/approve"
    )
    assert response2.status_code == 200


@pytest.mark.asyncio
@patch("src.services.admin.companies.enqueue_email_task")
async def test_reject_company_success(
    mock_enqueue_email, admin_client: AsyncClient, company_user
):
    """Test successfully rejecting a company."""
    mock_enqueue_email.return_value = "test-job-id"
    company_id = company_user.id

    response = await admin_client.post(f"/api/admin/companies/{company_id}/reject")
    assert response.status_code == 204

    # Verify user is deleted
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == company_id)  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one_or_none()
        assert user is None


@pytest.mark.asyncio
async def test_reject_company_not_found(admin_client: AsyncClient):
    """Test rejecting a non-existent company returns 404."""
    response = await admin_client.post("/api/admin/companies/99999/reject")
    assert response.status_code == 404
    assert response.json()["detail"].endswith("_not_found")


@pytest.mark.asyncio
@patch("src.services.admin.company_approval.enqueue_email_task")
@patch("src.services.admin.companies.enqueue_email_task")
async def test_reject_company_already_approved(
    mock_enqueue_email, mock_approval_email, admin_client: AsyncClient, company_user
):
    """Test rejecting after approval revokes the token and rejects the company (204)."""
    mock_enqueue_email.return_value = "test-job-id"
    mock_approval_email.return_value = "test-job-id"
    response1 = await admin_client.post(
        f"/api/admin/companies/{company_user.id}/approve"
    )
    assert response1.status_code == 200

    # Rejection after approval now succeeds — revokes the activation token
    response2 = await admin_client.post(
        f"/api/admin/companies/{company_user.id}/reject"
    )
    assert response2.status_code == 204


@pytest.mark.asyncio
async def test_admin_company_endpoints_require_auth(
    unauthenticated_client: AsyncClient,
):
    """Admin company endpoints reject requests without an auth token."""
    response = await unauthenticated_client.get("/api/admin/companies/pending")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_company_endpoints_require_admin_role(
    company_role_client: AsyncClient,
):
    """Admin company endpoints reject a COMPANY-role token with 403."""
    response = await company_role_client.get("/api/admin/companies/pending")
    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()


# ── admin-create / get-detail / edit by profile id ─────────────────────────────


_ADMIN_CREATE_PAYLOAD = {
    "name": "חברה ישירה",
    "company_id": "987654321",
    "address": "רח׳ הישר 7, חיפה",
    "contact_email": "yashir@example.com",
    "contact_first_name": "אורי",
    "contact_last_name": "ישיר",
    "contact_mobile_phone": "0508887777",
}


@pytest.mark.asyncio
async def test_admin_create_company_returns_profile_without_user(
    admin_client: AsyncClient,
):
    response = await admin_client.post(
        "/api/admin/companies", json=_ADMIN_CREATE_PAYLOAD
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] is None
    assert data["name"] == "חברה ישירה"
    assert data["company_id"] == "987654321"
    assert isinstance(data["id"], int)


@pytest.mark.asyncio
async def test_admin_create_company_validates_company_id(admin_client: AsyncClient):
    bad = {**_ADMIN_CREATE_PAYLOAD, "company_id": "12345"}  # wrong length
    response = await admin_client.post("/api/admin/companies", json=bad)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_create_company_requires_admin(public_client: AsyncClient):
    response = await public_client.post(
        "/api/admin/companies", json=_ADMIN_CREATE_PAYLOAD
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_company_profile_by_id_admin_created(admin_client: AsyncClient):
    create = await admin_client.post("/api/admin/companies", json=_ADMIN_CREATE_PAYLOAD)
    profile_id = create.json()["id"]

    response = await admin_client.get(f"/api/admin/companies/profile/{profile_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == profile_id
    assert data["user_id"] is None
    assert data["name"] == "חברה ישירה"


@pytest.mark.asyncio
async def test_get_company_profile_not_found(admin_client: AsyncClient):
    response = await admin_client.get("/api/admin/companies/profile/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_company_profile_partial(admin_client: AsyncClient):
    create = await admin_client.post("/api/admin/companies", json=_ADMIN_CREATE_PAYLOAD)
    profile_id = create.json()["id"]

    response = await admin_client.put(
        f"/api/admin/companies/profile/{profile_id}",
        json={"name": "שם מעודכן", "contact_landline_phone": "04-1112233"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "שם מעודכן"
    assert data["contact_landline_phone"] == "04-1112233"
    # Untouched fields preserved
    assert data["company_id"] == "987654321"
    assert data["contact_mobile_phone"] == "0508887777"


@pytest.mark.asyncio
async def test_update_company_profile_validates_phone(admin_client: AsyncClient):
    create = await admin_client.post("/api/admin/companies", json=_ADMIN_CREATE_PAYLOAD)
    profile_id = create.json()["id"]

    response = await admin_client.put(
        f"/api/admin/companies/profile/{profile_id}",
        json={"contact_mobile_phone": "12345"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_company_profile_not_found(admin_client: AsyncClient):
    response = await admin_client.put(
        "/api/admin/companies/profile/99999", json={"name": "no"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_created_company_appears_in_active_list(admin_client: AsyncClient):
    """Admin-created profiles (user_id=null) must be visible in GET /admin/companies.

    This is the core regression guard for #345: the query used to INNER JOIN
    with the user table, making orphan profiles invisible to the admin UI.
    """
    create = await admin_client.post("/api/admin/companies", json=_ADMIN_CREATE_PAYLOAD)
    assert create.status_code == 201
    profile_id = create.json()["id"]

    list_response = await admin_client.get("/api/admin/companies")
    assert list_response.status_code == 200
    items = list_response.json()["items"]

    ids = [item["company_profile"]["id"] for item in items]
    assert profile_id in ids, "Admin-created company missing from active list"

    matched = next(i for i in items if i["company_profile"]["id"] == profile_id)
    assert matched["user"] is None


@pytest.mark.asyncio
async def test_admin_create_company_persists_across_sessions(admin_client: AsyncClient):
    """Profile created via POST /admin/companies is committed, not just flushed.

    Uses a separate DB session after the API call to confirm the row is durably
    on disk — guarding against a transaction-boundary regression where the
    service only flushes but never commits.
    """
    response = await admin_client.post(
        "/api/admin/companies", json=_ADMIN_CREATE_PAYLOAD
    )
    assert response.status_code == 201
    profile_id = response.json()["id"]

    async with TestSessionLocal() as separate_session:
        result = await separate_session.execute(
            select(CompanyProfile).where(CompanyProfile.id == profile_id)  # pyright: ignore[reportArgumentType]
        )
        persisted = result.scalar_one_or_none()

    assert persisted is not None, "Company profile was not committed to the database"
    assert persisted.user_id is None
    assert persisted.name == "חברה ישירה"


@pytest.mark.asyncio
async def test_company_profile_endpoints_require_admin(public_client: AsyncClient):
    create_resp = await public_client.post(
        "/api/admin/companies", json=_ADMIN_CREATE_PAYLOAD
    )
    get_resp = await public_client.get("/api/admin/companies/profile/1")
    put_resp = await public_client.put(
        "/api/admin/companies/profile/1", json={"name": "x"}
    )
    assert create_resp.status_code == 401
    assert get_resp.status_code == 401
    assert put_resp.status_code == 401
