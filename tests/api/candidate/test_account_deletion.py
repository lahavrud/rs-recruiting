"""API tests for the candidate account deletion endpoints (#611)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from rs_api.infrastructure.dependencies import get_current_candidate
from rs_api.main import app
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.security import get_password_hash, hash_token
from rs_shared.enums import UserRole
from rs_shared.models import AccountDeletionToken, CandidateProfile, User
from tests.conftest import TestSessionLocal

_NOW = datetime.now(timezone.utc)


async def _override_session():
    async with TestSessionLocal() as session:
        yield session


def _override_candidate(user: User, profile: CandidateProfile):
    async def _resolver() -> tuple[User, CandidateProfile]:
        return user, profile

    app.dependency_overrides[get_current_candidate] = _resolver


@pytest.fixture(autouse=True)
def _isolate():
    app.dependency_overrides[get_session] = _override_session
    yield
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_candidate, None)


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_candidate(email: str = "del@test.com") -> tuple[User, CandidateProfile]:
    async with TestSessionLocal() as session:
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
            full_name="Del Candidate",
            email=email,
        )
        session.add(profile)
        await session.commit()
        await session.refresh(user)
        await session.refresh(profile)
    return user, profile


async def _seed_deletion_token(
    profile: CandidateProfile,
    *,
    used: bool = False,
    expires_at: datetime | None = None,
) -> str:
    raw = secrets.token_urlsafe(32)
    async with TestSessionLocal() as session:
        rec = AccountDeletionToken(
            token_hash=hash_token(raw),
            candidate_profile_id=profile.id,
            expires_at=expires_at or (_NOW + timedelta(hours=24)),
            used=used,
        )
        session.add(rec)
        await session.commit()
    return raw


# ---------------------------------------------------------------------------
# POST /api/candidate/me/deletion-request (authenticated)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticated_deletion_request_returns_202(test_db):
    user, profile = await _seed_candidate("auth-del@test.com")
    _override_candidate(user, profile)

    with patch("rs_shared.services.candidate.account_deletion.defer_after_commit"):
        async with await _client() as client:
            resp = await client.post("/api/candidate/me/deletion-request")

    assert resp.status_code == 202


# ---------------------------------------------------------------------------
# POST /api/candidate/deletion-request (anonymous)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anonymous_deletion_request_returns_202_for_known_email(test_db):
    _, profile = await _seed_candidate("anon-del@test.com")

    with patch("rs_shared.services.candidate.account_deletion.defer_after_commit"):
        async with await _client() as client:
            resp = await client.post(
                "/api/candidate/deletion-request",
                json={"email": "anon-del@test.com"},
            )

    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_anonymous_deletion_request_returns_202_for_unknown_email(test_db):
    """Email-enumeration protection: always 202, even for missing emails."""
    async with await _client() as client:
        resp = await client.post(
            "/api/candidate/deletion-request",
            json={"email": "nobody@test.com"},
        )

    assert resp.status_code == 202


# ---------------------------------------------------------------------------
# GET /api/candidate/deletion-confirm
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_token_returns_200_for_valid_token(test_db):
    _, profile = await _seed_candidate("chkv@test.com")
    raw = await _seed_deletion_token(profile)

    async with await _client() as client:
        resp = await client.get(
            "/api/candidate/deletion-confirm", params={"token": raw}
        )

    assert resp.status_code == 200
    assert resp.json()["valid"] is True


@pytest.mark.asyncio
async def test_validate_token_returns_400_for_expired_token(test_db):
    _, profile = await _seed_candidate("chkexp@test.com")
    raw = await _seed_deletion_token(profile, expires_at=_NOW - timedelta(hours=1))

    async with await _client() as client:
        resp = await client.get(
            "/api/candidate/deletion-confirm", params={"token": raw}
        )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_deletion_token"


@pytest.mark.asyncio
async def test_validate_token_returns_400_for_unknown_token(test_db):
    async with await _client() as client:
        resp = await client.get(
            "/api/candidate/deletion-confirm",
            params={"token": "not-a-real-token"},
        )

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/candidate/deletion-confirm
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_deletion_returns_204(test_db):
    user, profile = await _seed_candidate("conf@test.com")
    raw = await _seed_deletion_token(profile)

    mock_storage = MagicMock()
    mock_storage.delete_file = AsyncMock(return_value=True)

    with patch(
        "rs_api.api.candidate.account_deletion.get_storage_provider",
        return_value=mock_storage,
    ):
        async with await _client() as client:
            resp = await client.post(
                "/api/candidate/deletion-confirm", json={"token": raw}
            )

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_confirm_deletion_returns_400_for_invalid_token(test_db):
    mock_storage = MagicMock()
    mock_storage.delete_file = AsyncMock(return_value=True)

    with patch(
        "rs_api.api.candidate.account_deletion.get_storage_provider",
        return_value=mock_storage,
    ):
        async with await _client() as client:
            resp = await client.post(
                "/api/candidate/deletion-confirm",
                json={"token": "invalid-token"},
            )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_deletion_token"


@pytest.mark.asyncio
async def test_confirm_deletion_returns_400_on_token_reuse(test_db):
    user, profile = await _seed_candidate("reuse@test.com")
    raw = await _seed_deletion_token(profile)

    mock_storage = MagicMock()
    mock_storage.delete_file = AsyncMock(return_value=True)

    with patch(
        "rs_api.api.candidate.account_deletion.get_storage_provider",
        return_value=mock_storage,
    ):
        async with await _client() as client:
            resp1 = await client.post(
                "/api/candidate/deletion-confirm", json={"token": raw}
            )
        assert resp1.status_code == 204

        async with await _client() as client:
            resp2 = await client.post(
                "/api/candidate/deletion-confirm", json={"token": raw}
            )
    assert resp2.status_code == 400
