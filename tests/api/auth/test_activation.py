"""Tests for the company account activation endpoint."""

import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.main import app
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.security import get_password_hash, hash_token
from rs_shared.enums import UserRole
from rs_shared.models import ActivationToken, CandidateProfile, CompanyProfile, User
from tests.conftest import TestSessionLocal


async def _override_session():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_session] = _override_session


async def _make_pending_company(session: AsyncSession) -> tuple[User, str]:
    """Create an inactive company user + unused activation token.

    Does NOT commit — callers keep the session open so that concurrent
    xdist workers' TRUNCATE teardowns cannot delete the rows before the
    ASGI activation request reads them.
    """
    email = f"activation-{secrets.token_hex(6)}@test.com"
    user = User(
        email=email,
        hashed_password=get_password_hash("Password1!"),
        role=UserRole.COMPANY,
        is_active=False,
    )
    session.add(user)
    await session.flush()

    profile = CompanyProfile(
        user_id=user.id,
        name="Test Co",
        company_id="123456789",
        address="רח׳ הדוגמה 1, תל אביב",
        contact_email=email,
        contact_first_name="ישראל",
        contact_last_name="ישראלי",
        contact_mobile_phone="0501234567",
    )
    session.add(profile)
    await session.flush()

    raw_token = secrets.token_urlsafe(32)
    activation = ActivationToken(
        token_hash=hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        used=False,
    )
    session.add(activation)
    await session.flush()  # flush but do NOT commit yet
    return user, raw_token


@pytest.mark.asyncio
async def test_activate_valid_token(test_db):
    async with TestSessionLocal() as session:
        user, token = await _make_pending_company(session)

        # Inject the same open session into the app so the ASGI request sees
        # uncommitted rows — preventing concurrent TRUNCATE from wiping them.
        async def _use_this_session() -> AsyncSession:
            yield session

        app.dependency_overrides[get_session] = _use_this_session

        with patch("rs_shared.services.admin.companies.queue_email"):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(f"/auth/activate?token={token}")

    app.dependency_overrides[get_session] = _override_session  # restore

    assert resp.status_code == 200
    assert resp.json() == {"message": "החשבון הופעל בהצלחה"}


@pytest.mark.asyncio
async def test_activate_invalid_token_returns_400():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/auth/activate?token=nonexistent-token")

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_activate_used_token_returns_400(test_db):
    async with TestSessionLocal() as session:
        user, token = await _make_pending_company(session)

        async def _use_this_session() -> AsyncSession:
            yield session

        app.dependency_overrides[get_session] = _use_this_session

        # Mark the token as already used while session is still open
        from sqlalchemy import select

        result = await session.execute(
            select(ActivationToken).where(
                ActivationToken.token_hash == hash_token(token)  # type: ignore[arg-type]
            )
        )
        act = result.scalar_one()
        act.used = True
        await session.flush()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(f"/auth/activate?token={token}")

    app.dependency_overrides[get_session] = _override_session

    assert resp.status_code == 400


async def _make_pending_candidate(
    session: AsyncSession, *, full_name: str | None = None
) -> tuple[User, str]:
    """Inactive candidate user + unused activation token, session-flushed only."""
    email = f"candidate-act-{secrets.token_hex(6)}@test.com"
    user = User(
        email=email,
        hashed_password=get_password_hash("Password1!"),  # pragma: allowlist secret
        role=UserRole.CANDIDATE,
        is_active=False,
    )
    session.add(user)
    await session.flush()

    raw_token = secrets.token_urlsafe(32)
    activation = ActivationToken(
        token_hash=hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        used=False,
        full_name=full_name,
    )
    session.add(activation)
    await session.flush()
    return user, raw_token


@pytest.mark.asyncio
async def test_activate_candidate_returns_200_and_enqueues_welcome(test_db):
    """Regression for the activation 500 (candidate cohort).

    Bug: the welcome-email ``defer_after_commit`` call lived *after* the
    ``async with transactional(session)`` block exited, so the contextvar
    had already been reset to its sentinel and the call raised
    ``RuntimeError``. The transaction had already committed by then —
    the token was marked used and ``is_active`` flipped to True — but the
    HTTP response came back 500. The frontend interpreted that as
    "token invalid" and the user retried registration, which then 409'd
    because the user was actually active.

    Assert both observable outcomes:
      * the route returns 200 (no RuntimeError leaked)
      * the welcome email enqueue actually ran (proves the hook fired
        inside transactional()'s post-commit pass, not into a phantom
        contextvar list that never gets executed).
    """
    async with TestSessionLocal() as session:
        user, token = await _make_pending_candidate(session)

        async def _use_this_session() -> AsyncSession:
            yield session

        app.dependency_overrides[get_session] = _use_this_session

        with patch(
            "rs_api.api.auth.activation.queue_email",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(f"/auth/activate?token={token}")

    app.dependency_overrides[get_session] = _override_session

    assert resp.status_code == 200
    mock_enqueue.assert_awaited_once()
    enqueue_kwargs = mock_enqueue.await_args.kwargs
    assert enqueue_kwargs["to"] == user.email
    assert "ברוכים" in enqueue_kwargs["subject"]


@pytest.mark.asyncio
async def test_activate_candidate_links_existing_profile_and_writes_consent(test_db):
    """An anonymous-lead CandidateProfile (no user_id) gets linked at activation."""
    async with TestSessionLocal() as session:
        user, token = await _make_pending_candidate(session)
        # Pre-existing anonymous lead: same email, no user_id yet.
        lead = CandidateProfile(
            user_id=None,
            full_name="Existing Lead",
            email=user.email,
            phone="050-000-0000",
        )
        session.add(lead)
        await session.flush()

        async def _use_this_session() -> AsyncSession:
            yield session

        app.dependency_overrides[get_session] = _use_this_session

        with patch(
            "rs_api.api.auth.activation.queue_email",
            new_callable=AsyncMock,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(f"/auth/activate?token={token}")

        await session.refresh(lead)
        assert resp.status_code == 200
        assert lead.user_id == user.id
        assert lead.consent_given_at is not None

    app.dependency_overrides[get_session] = _override_session


@pytest.mark.asyncio
async def test_activate_candidate_prefills_profile_full_name_from_token(test_db):
    """``CandidateProfile.full_name`` reads the snapshot off ActivationToken.

    Prior behavior used ``email.split("@")[0]`` as a placeholder, which the
    user then had to retype on the profile page. The follow-up snapshots
    the registered name onto the token at registration time and reads it
    here.
    """
    async with TestSessionLocal() as session:
        user, token = await _make_pending_candidate(session, full_name="Real Person")

        async def _use_this_session() -> AsyncSession:
            yield session

        app.dependency_overrides[get_session] = _use_this_session

        with patch(
            "rs_api.api.auth.activation.queue_email",
            new_callable=AsyncMock,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(f"/auth/activate?token={token}")

        from sqlmodel import select as _select

        profile = (
            await session.execute(
                _select(CandidateProfile).where(  # type: ignore[arg-type]
                    CandidateProfile.user_id == user.id
                )
            )
        ).scalar_one()

    app.dependency_overrides[get_session] = _override_session

    assert resp.status_code == 200
    assert profile.full_name == "Real Person"


@pytest.mark.asyncio
async def test_activate_candidate_falls_back_to_email_prefix_when_no_name(
    test_db,
):
    """Legacy tokens minted before ``full_name`` existed still activate cleanly."""
    async with TestSessionLocal() as session:
        user, token = await _make_pending_candidate(session, full_name=None)

        async def _use_this_session() -> AsyncSession:
            yield session

        app.dependency_overrides[get_session] = _use_this_session

        with patch(
            "rs_api.api.auth.activation.queue_email",
            new_callable=AsyncMock,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(f"/auth/activate?token={token}")

        from sqlmodel import select as _select

        profile = (
            await session.execute(
                _select(CandidateProfile).where(  # type: ignore[arg-type]
                    CandidateProfile.user_id == user.id
                )
            )
        ).scalar_one()

    app.dependency_overrides[get_session] = _override_session

    assert resp.status_code == 200
    assert profile.full_name == user.email.split("@", 1)[0]


@pytest.mark.asyncio
async def test_activate_rate_limit_returns_429_after_five_attempts():
    """POST /auth/activate is capped at 5 requests/hour per IP.

    Uses an invalid token so the handler returns 400 on each of the first
    five attempts; the sixth attempt hits the rate limit and returns 429.
    The limiter is enabled only for this test and storage is cleared
    before and after to avoid interfering with sibling tests.
    """
    from rs_api.api.auth import activation

    activation.limiter.enabled = True
    activation.limiter._storage.reset()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(5):
                r = await client.post("/auth/activate?token=fake-token")
                assert r.status_code == 400

            rate_limited = await client.post("/auth/activate?token=fake-token")

        assert rate_limited.status_code == 429
    finally:
        activation.limiter._storage.reset()
        activation.limiter.enabled = False
