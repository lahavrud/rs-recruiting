"""API tests for /api/candidate/me + resume endpoints (Sprint 11 / #608)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.infrastructure.dependencies import get_current_candidate, get_current_user
from rs_api.main import app
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.security import get_password_hash
from rs_shared.enums import UserRole
from rs_shared.models import CandidateProfile, User
from tests.conftest import TestSessionLocal, audit_rows


async def _override_session():
    async with TestSessionLocal() as session:
        yield session


# Re-applied per-test because shared fixtures elsewhere in the suite call
# ``app.dependency_overrides.clear()`` on teardown, which would wipe a
# module-level assignment and route subsequent requests through the
# production engine.
@pytest.fixture(autouse=True)
def _install_session_override():
    app.dependency_overrides[get_session] = _override_session
    yield
    app.dependency_overrides.pop(get_session, None)


async def _seed_candidate(
    session: AsyncSession, email: str = "me@test.com"
) -> tuple[User, CandidateProfile]:
    user = User(
        email=email,
        hashed_password=get_password_hash("Secret1!"),  # pragma: allowlist secret
        role=UserRole.CANDIDATE,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    profile = CandidateProfile(
        user_id=user.id,
        full_name="Me Test",
        email=email,
        phone="050-000-0001",
        linkedin_url="https://linkedin.com/in/me",
    )
    session.add(profile)
    await session.commit()
    await session.refresh(user)
    await session.refresh(profile)
    return user, profile


def _override_user(user_id: int, email: str):
    """Override only ``get_current_user`` so the chain's profile lookup
    runs against the request's session (avoids cross-session attach errors)."""

    async def _resolver() -> User:
        from rs_shared.enums import UserRole as _UR

        # Minimal stub — enough for get_current_candidate to verify role and
        # filter the profile lookup by user_id.
        return User(
            id=user_id,
            email=email,
            hashed_password="x",  # pragma: allowlist secret
            role=_UR.CANDIDATE,
            is_active=True,
        )

    app.dependency_overrides[get_current_user] = _resolver


@pytest.fixture(autouse=True)
def _isolate_dep_overrides():
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_candidate, None)


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_get_me_returns_profile_with_user_email(test_db):
    async with TestSessionLocal() as session:
        user, profile = await _seed_candidate(session, "get-me@test.com")
        _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.get("/api/candidate/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "get-me@test.com"
    assert body["full_name"] == "Me Test"
    assert body["linkedin_url"] == "https://linkedin.com/in/me"


@pytest.mark.asyncio
async def test_patch_me_updates_allowed_fields(test_db):
    async with TestSessionLocal() as session:
        user, profile = await _seed_candidate(session, "patch@test.com")
        _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.patch(
            "/api/candidate/me",
            json={"full_name": "New Name", "phone": "052-111-2233"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "New Name"
    assert body["phone"] == "052-111-2233"

    # The candidate is the actor; only the field names are recorded.
    [row] = await audit_rows("candidate.profile_update")
    assert (row.target_id, row.actor_user_id, row.ip_address) == (
        profile.id,
        user.id,
        "127.0.0.1",
    )
    assert row.detail == "fields=full_name,phone"


@pytest.mark.asyncio
async def test_patch_me_rejects_email_change_with_400(test_db):
    async with TestSessionLocal() as session:
        user, profile = await _seed_candidate(session, "email-locked@test.com")
        _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.patch(
            "/api/candidate/me",
            json={"email": "spoof@test.com", "full_name": "Hacker"},
        )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "email_not_editable"


@pytest.mark.asyncio
async def test_patch_me_rejects_invalid_phone(test_db):
    async with TestSessionLocal() as session:
        user, profile = await _seed_candidate(session, "bad-phone@test.com")
        _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.patch(
            "/api/candidate/me",
            json={"phone": "not-a-phone"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_resume_upload_then_delete_roundtrip(test_db):
    async with TestSessionLocal() as session:
        user, profile = await _seed_candidate(session, "resume@test.com")
        _override_user(user.id, user.email)

    mock_storage = AsyncMock()
    mock_storage.upload_file = AsyncMock(return_value="resumes/new-key.pdf")
    mock_storage.delete_file = AsyncMock(return_value=True)

    pdf_bytes = b"%PDF-1.4" + b"\x00" * 100

    with patch(
        "rs_api.api.candidate.profile.get_storage_provider", return_value=mock_storage
    ):
        async with await _client() as client:
            up = await client.post(
                "/api/candidate/me/resume",
                files={"resume": ("cv.pdf", pdf_bytes, "application/pdf")},
            )
            assert up.status_code == 200
            assert up.json()["resume_path"] == "resumes/new-key.pdf"

            rm = await client.delete("/api/candidate/me/resume")
            assert rm.status_code == 200
            assert rm.json()["resume_path"] is None
            mock_storage.delete_file.assert_awaited()


@pytest.mark.asyncio
async def test_resume_upload_rejects_wrong_extension(test_db):
    async with TestSessionLocal() as session:
        user, profile = await _seed_candidate(session, "bad-ext@test.com")
        _override_user(user.id, user.email)

    mock_storage = AsyncMock()
    with patch(
        "rs_api.api.candidate.profile.get_storage_provider", return_value=mock_storage
    ):
        async with await _client() as client:
            resp = await client.post(
                "/api/candidate/me/resume",
                files={"resume": ("doc.txt", b"plain text", "text/plain")},
            )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "unsupported_file_type"
    mock_storage.upload_file.assert_not_called()


@pytest.mark.asyncio
async def test_resume_upload_rejects_oversized_file(test_db):
    """Profile resume upload rejects files over 10 MB with 413."""
    async with TestSessionLocal() as session:
        user, profile = await _seed_candidate(session, "big-file@test.com")
        _override_user(user.id, user.email)

    mock_storage = AsyncMock()
    large_content = b"%PDF-1.4" + b"x" * (11 * 1024 * 1024)
    with patch(
        "rs_api.api.candidate.profile.get_storage_provider", return_value=mock_storage
    ):
        async with await _client() as client:
            resp = await client.post(
                "/api/candidate/me/resume",
                files={"resume": ("big.pdf", large_content, "application/pdf")},
            )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "file_too_large"
    mock_storage.upload_file.assert_not_called()
