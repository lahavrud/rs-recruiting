"""API tests for the candidate self-registration + resend-activation endpoints
(Sprint 11 / issue #605)."""

import secrets
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from rs_api.main import app
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.security import get_password_hash
from rs_shared.enums import UserRole
from rs_shared.models import ActivationToken, AuditLog, User
from tests.conftest import TestSessionLocal


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


@pytest.fixture
def _patch_enqueue_email():
    with patch(
        "rs_shared.services.auth.candidate_registration.queue_email",
        new_callable=AsyncMock,
    ) as p:
        yield p


@pytest.fixture
def _patch_activation_email():
    with patch(
        "rs_api.api.auth.activation.queue_email",
        new_callable=AsyncMock,
    ) as p:
        yield p


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _unique_email() -> str:
    return f"cand-{secrets.token_hex(4)}@test.com"


# --------------------------------------------------------------------------
# /auth/candidate/register
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_creates_pending_user_and_token(test_db, _patch_enqueue_email):
    email = _unique_email()
    async with await _client() as client:
        resp = await client.post(
            "/auth/candidate/register",
            json={
                "email": email,
                "password": "SecurePass1!",  # pragma: allowlist secret
                "full_name": "Test Candidate",
                "privacy_accepted": True,
                "terms_accepted": True,
            },
        )

    assert resp.status_code == 201
    assert "message" in resp.json()

    async with TestSessionLocal() as session:
        user = (
            await session.execute(
                select(User).where(User.email == email)  # type: ignore[arg-type]
            )
        ).scalar_one()
        assert user.role == UserRole.CANDIDATE
        assert user.is_active is False

        tokens = (
            (
                await session.execute(
                    select(ActivationToken).where(
                        ActivationToken.user_id == user.id  # type: ignore[arg-type]
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(tokens) == 1
        assert tokens[0].consent_policy_version is not None
        # Token TTL is 2 hours — assert it lands in (1.9, 2.1) hours window.
        delta = tokens[0].expires_at.replace(tzinfo=timezone.utc) - datetime.now(
            timezone.utc
        )
        assert 1.9 * 3600 < delta.total_seconds() < 2.1 * 3600

    _patch_enqueue_email.assert_awaited()


@pytest.mark.asyncio
async def test_register_rejects_active_email_with_409(test_db, _patch_enqueue_email):
    """Active-account collision returns 409 so the UI can prompt the user
    to log in instead of silently swallowing the attempt."""
    email = _unique_email()
    async with TestSessionLocal() as session:
        session.add(
            User(
                email=email,
                hashed_password=get_password_hash(  # pragma: allowlist secret
                    "Existing1!"
                ),
                role=UserRole.CANDIDATE,
                is_active=True,
            )
        )
        await session.commit()

    async with await _client() as client:
        resp = await client.post(
            "/auth/candidate/register",
            json={
                "email": email,
                "password": "AnotherPass1!",  # pragma: allowlist secret
                "full_name": "Hijack Attempt",
                "privacy_accepted": True,
                "terms_accepted": True,
            },
        )

    assert resp.status_code == 409
    _patch_enqueue_email.assert_not_called()


@pytest.mark.asyncio
async def test_register_rejects_pending_company_email_with_409(
    test_db, _patch_enqueue_email
):
    """An email registered for a pending company cannot be hijacked by
    the candidate flow. Surface that to the UI as a 409, same as the
    active-account branch — the user needs to know they can't register
    that address."""
    email = _unique_email()
    async with TestSessionLocal() as session:
        session.add(
            User(
                email=email,
                hashed_password=get_password_hash(  # pragma: allowlist secret
                    "Existing1!"
                ),
                role=UserRole.COMPANY,
                is_active=False,
            )
        )
        await session.commit()

    async with await _client() as client:
        resp = await client.post(
            "/auth/candidate/register",
            json={
                "email": email,
                "password": "AnotherPass1!",  # pragma: allowlist secret
                "full_name": "Hijack Attempt",
                "privacy_accepted": True,
                "terms_accepted": True,
            },
        )

    assert resp.status_code == 409
    _patch_enqueue_email.assert_not_called()

    async with TestSessionLocal() as session:
        existing = (
            await session.execute(
                select(User).where(User.email == email)  # type: ignore[arg-type]
            )
        ).scalar_one()
        assert existing.role == UserRole.COMPANY
        assert existing.is_active is False


@pytest.mark.asyncio
async def test_register_recycles_pending_candidate_and_kills_old_token(
    test_db, _patch_enqueue_email
):
    """Submitting the same email twice while is_active=False updates the
    password and replaces the old token — mirrors the locked Sprint 11 spec."""
    email = _unique_email()
    async with TestSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash("OldPass1!"),
            role=UserRole.CANDIDATE,
            is_active=False,
        )
        session.add(user)
        await session.flush()
        session.add(
            ActivationToken(
                token_hash="old-hash",
                user_id=user.id,
                expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            )
        )
        await session.commit()

    async with await _client() as client:
        resp = await client.post(
            "/auth/candidate/register",
            json={
                "email": email,
                "password": "FreshPass1!",  # pragma: allowlist secret
                "full_name": "Fresh Reg",
                "privacy_accepted": True,
                "terms_accepted": True,
            },
        )

    assert resp.status_code == 201
    async with TestSessionLocal() as session:
        tokens = (
            (
                await session.execute(
                    select(ActivationToken).where(
                        ActivationToken.user_id
                        == (
                            await session.execute(
                                select(User.id).where(User.email == email)  # type: ignore[arg-type]
                            )
                        ).scalar_one()
                    )
                )
            )
            .scalars()
            .all()
        )
        # Old token deleted, new fresh one in its place.
        assert len(tokens) == 1
        assert tokens[0].token_hash != "old-hash"


@pytest.mark.asyncio
async def test_register_requires_consent(test_db, _patch_enqueue_email):
    async with await _client() as client:
        resp = await client.post(
            "/auth/candidate/register",
            json={
                "email": _unique_email(),
                "password": "SecurePass1!",  # pragma: allowlist secret
                "full_name": "No Consent",
                "privacy_accepted": False,
                "terms_accepted": True,
            },
        )
    assert resp.status_code == 422
    _patch_enqueue_email.assert_not_called()


@pytest.mark.asyncio
async def test_register_audits_request(test_db, _patch_enqueue_email):
    """Audit row `candidate_register_requested` exists after success."""
    email = _unique_email()
    async with await _client() as client:
        resp = await client.post(
            "/auth/candidate/register",
            json={
                "email": email,
                "password": "SecurePass1!",  # pragma: allowlist secret
                "full_name": "Audit Me",
                "privacy_accepted": True,
                "terms_accepted": True,
            },
        )
    assert resp.status_code == 201

    async with TestSessionLocal() as session:
        user = (
            await session.execute(
                select(User).where(User.email == email)  # type: ignore[arg-type]
            )
        ).scalar_one()
        audit = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.actor_user_id == user.id,  # type: ignore[arg-type]
                    AuditLog.action == "candidate_register_requested",  # type: ignore[arg-type]
                )
            )
        ).scalar_one()
        assert audit is not None
        assert "Audit Me" in (audit.detail or "")


# --------------------------------------------------------------------------
# /auth/candidate/resend-activation
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resend_for_pending_candidate_mints_fresh_token(
    test_db, _patch_enqueue_email
):
    email = _unique_email()
    async with TestSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash("Old1!"),
            role=UserRole.CANDIDATE,
            is_active=False,
        )
        session.add(user)
        await session.flush()
        from datetime import timedelta

        session.add(
            ActivationToken(
                token_hash="old-resend-hash",
                user_id=user.id,
                expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
                # Outside the 1-hour rate-limit window so the resend is not blocked
                created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            )
        )
        await session.commit()
        user_id = user.id

    async with await _client() as client:
        resp = await client.post(
            "/auth/candidate/resend-activation",
            json={"email": email},
        )

    assert resp.status_code == 202
    async with TestSessionLocal() as session:
        tokens = (
            (
                await session.execute(
                    select(ActivationToken).where(
                        ActivationToken.user_id == user_id  # type: ignore[arg-type]
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(tokens) == 1
        assert tokens[0].token_hash != "old-resend-hash"
    _patch_enqueue_email.assert_awaited()


@pytest.mark.asyncio
async def test_resend_for_active_user_is_silent(test_db, _patch_enqueue_email):
    email = _unique_email()
    async with TestSessionLocal() as session:
        session.add(
            User(
                email=email,
                hashed_password=get_password_hash("Active1!"),
                role=UserRole.CANDIDATE,
                is_active=True,
            )
        )
        await session.commit()

    async with await _client() as client:
        resp = await client.post(
            "/auth/candidate/resend-activation",
            json={"email": email},
        )

    assert resp.status_code == 202
    _patch_enqueue_email.assert_not_called()


@pytest.mark.asyncio
async def test_resend_for_unknown_email_is_silent(test_db, _patch_enqueue_email):
    async with await _client() as client:
        resp = await client.post(
            "/auth/candidate/resend-activation",
            json={"email": _unique_email()},
        )
    assert resp.status_code == 202
    _patch_enqueue_email.assert_not_called()


@pytest.mark.asyncio
async def test_resend_throttles_per_email(test_db, _patch_enqueue_email):
    """When the DB counter shows the user hit the window quota, resend is a no-op."""
    email = _unique_email()
    async with TestSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash("X1!"),
            role=UserRole.CANDIDATE,
            is_active=False,
        )
        session.add(user)
        await session.flush()
        # Seed one token in the last-hour window — hits the 1/hour cap
        session.add(
            ActivationToken(
                token_hash=f"throttle-seed-{email}",
                user_id=user.id,
                expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            )
        )
        await session.commit()

    async with await _client() as client:
        resp = await client.post(
            "/auth/candidate/resend-activation",
            json={"email": email},
        )

    assert resp.status_code == 202
    _patch_enqueue_email.assert_not_called()
