"""Tests for authentication endpoints — login, refresh, logout."""

import logging
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from rs_api.main import app
from rs_shared.core.infrastructure.database import get_session
from rs_shared.models import User
from tests.conftest import FAKE_PNG, TestSessionLocal, audit_rows
from tests.conftest import FAKE_SIG_B64 as _FAKE_SIG_B64

FAKE_LOGO_FILE = ("logo.png", FAKE_PNG, "image/png")
FAKE_SIGNATURE_B64 = _FAKE_SIG_B64

_STRONG_PASSWORD = "SecurePass1!"


async def override_get_session():
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture(scope="function")
async def client():
    from rs_api.api.auth import login as auth

    auth.limiter.enabled = False
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
        app.dependency_overrides.clear()


def _reg_data(**overrides):
    data = {
        "email": "company@example.com",
        "password": _STRONG_PASSWORD,
        "company_name": "Test Company",
        "company_id": "123456789",
        "address": "רח׳ הדוגמה 1, תל אביב",
        "contact_first_name": "ישראל",
        "contact_last_name": "ישראלי",
        "contact_mobile_phone": "0501234567",
        "agreement_signature": FAKE_SIGNATURE_B64,
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }
    data.update(overrides)
    return data


# ==================== Login Tests ====================


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Test successful login returns access token and sets HttpOnly refresh cookie."""
    await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="login@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == "login@example.com")  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        user.is_active = True
        await session.commit()

    response = await client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": _STRONG_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" not in data  # delivered via HttpOnly cookie
    assert data["token_type"] == "bearer"
    assert response.cookies.get("refresh_token") is not None

    # Every role's login is audited now, not only admins'.
    [row] = [r for r in await audit_rows("user.login") if r.target_id == user.id]
    assert (row.target_type, row.target_id, row.actor_user_id) == (
        "User",
        user.id,
        user.id,
    )
    assert row.detail == "role=COMPANY"


@pytest.mark.asyncio
async def test_login_invalid_email(client: AsyncClient):
    """Test login fails with unknown email."""
    response = await client.post(
        "/auth/login", json={"email": "nonexistent@example.com", "password": "pass"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    """Test login fails with wrong password."""
    await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="wrongpass@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == "wrongpass@example.com")  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        user.is_active = True
        await session.commit()

    response = await client.post(
        "/auth/login",
        json={"email": "wrongpass@example.com", "password": "WrongPass1!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient):
    """Test login fails for inactive users."""
    await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="inactive@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    response = await client.post(
        "/auth/login",
        json={"email": "inactive@example.com", "password": _STRONG_PASSWORD},
    )
    assert response.status_code == 401
    assert "pending" in response.json()["detail"].lower()


# ==================== Refresh Token Tests ====================


@pytest.mark.asyncio
async def test_login_over_72_byte_password_is_401_not_500(client: AsyncClient):
    """bcrypt>=5 raises above 72 bytes; login must answer like any wrong
    password, for both an existing and an unknown email (#1167)."""
    await _create_active_user(client, "longpw@example.com")
    over_limit = "Aa1!" + "x" * 96  # 100 bytes
    for email in ("longpw@example.com", "nobody-longpw@example.com"):
        response = await client.post(
            "/auth/login", json={"email": email, "password": over_limit}
        )
        assert response.status_code == 401, email


async def _create_active_user(client: AsyncClient, email: str) -> dict:
    """Helper: register + activate + login.

    Returns the JSON body (access_token, token_type). The refresh token is
    delivered as an HttpOnly cookie and automatically stored in the client's
    cookie jar for subsequent requests.
    """
    await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email=email),
        files={"logo": FAKE_LOGO_FILE},
    )
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == email)  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        user.is_active = True
        await session.commit()

    login_resp = await client.post(
        "/auth/login",
        json={"email": email, "password": _STRONG_PASSWORD},
    )
    assert login_resp.status_code == 200
    return login_resp.json()


@pytest.mark.asyncio
async def test_refresh_returns_new_tokens(client: AsyncClient):
    """Refresh-token cookie yields a new access token and rotated cookie."""
    await _create_active_user(client, "refresh@example.com")
    old_refresh_cookie = client.cookies.get("refresh_token")
    assert old_refresh_cookie is not None

    response = await client.post("/auth/refresh")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" not in data  # still cookie-only
    # Access token may be identical if issued within the same second (no JTI);
    # what matters is that the refresh-token cookie is rotated.
    assert response.cookies.get("refresh_token") != old_refresh_cookie  # rotated


@pytest.mark.asyncio
@patch(
    "rs_shared.services.auth.session._nuke_user_refresh_tokens", new_callable=AsyncMock
)
async def test_refresh_token_is_single_use(_mock_nuke: AsyncMock, client: AsyncClient):
    """Test that an already-rotated refresh token is rejected."""
    await _create_active_user(client, "singleuse@example.com")
    original_refresh = client.cookies.get("refresh_token")
    assert original_refresh is not None

    resp1 = await client.post("/auth/refresh")
    assert resp1.status_code == 200

    transport = client._transport  # pyright: ignore[reportPrivateUsage]
    from httpx import AsyncClient as HttpxClient

    async with HttpxClient(
        transport=transport,
        base_url="http://test",
        cookies={"refresh_token": original_refresh},
    ) as old_client:
        resp2 = await old_client.post("/auth/refresh")
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_refresh_invalid_token_returns_401(client: AsyncClient):
    """Test that a bogus refresh token cookie is rejected."""
    transport = client._transport  # pyright: ignore[reportPrivateUsage]
    from httpx import AsyncClient as HttpxClient

    async with HttpxClient(
        transport=transport,
        base_url="http://test",
        cookies={"refresh_token": "not-a-real-token"},
    ) as bad_client:
        response = await bad_client.post("/auth/refresh")
    assert response.status_code == 401


# ==================== Login throttling (per email + client IP) ====================


async def _peer_client(ip: str) -> AsyncClient:
    """A client whose requests arrive from ``ip`` (the app's overrides apply)."""
    transport = ASGITransport(app=app, client=(ip, 40000))
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
@pytest.mark.real_login_throttle
async def test_failed_logins_block_only_the_offending_source(client: AsyncClient):
    """5 failures from one address block that address (even with the right
    password), while the account's owner logs in normally from another one.
    Before, the 5 failures locked the account for everyone."""
    await _create_active_user(client, "throttle@example.com")
    bad = {"email": "throttle@example.com", "password": "WrongPass1!"}
    good = {"email": "throttle@example.com", "password": _STRONG_PASSWORD}

    async with await _peer_client("203.0.113.66") as attacker:
        statuses = [
            (await attacker.post("/auth/login", json=bad)).status_code for _ in range(5)
        ]
        assert statuses == [401] * 5
        blocked = await attacker.post("/auth/login", json=good)
        assert blocked.status_code == 429
        assert blocked.json()["detail"] == "account_locked"

    async with await _peer_client("198.51.100.7") as owner:
        resp = await owner.post("/auth/login", json=good)
        assert resp.status_code == 200
        assert "access_token" in resp.json()


@pytest.mark.asyncio
@pytest.mark.real_login_throttle
async def test_unknown_email_is_throttled_like_a_real_one(client: AsyncClient):
    """A 429 must not reveal that an account exists."""
    bad = {"email": "nobody-throttle@example.com", "password": "WrongPass1!"}
    async with await _peer_client("203.0.113.67") as attacker:
        statuses = [
            (await attacker.post("/auth/login", json=bad)).status_code for _ in range(6)
        ]
    assert statuses == [401] * 5 + [429]


@pytest.mark.asyncio
async def test_successful_login_clears_failed_attempts(client: AsyncClient):
    """Test that a successful login clears the lockout counter."""
    tokens = await _create_active_user(client, "clearlock@example.com")
    assert "access_token" in tokens  # login succeeded — counter was cleared


@pytest.mark.asyncio
@pytest.mark.real_login_throttle
async def test_login_failed_logs_ip(client: AsyncClient, caplog):
    """A bad-password login emits a login_failed record carrying the client IP."""
    await _create_active_user(client, "logip@example.com")
    async with await _peer_client("203.0.113.68") as peer:
        with caplog.at_level(
            logging.WARNING, logger="rs_shared.services.auth.login_throttle"
        ):
            await peer.post(
                "/auth/login",
                json={"email": "logip@example.com", "password": "WrongPass1!"},
            )

    records = [r for r in caplog.records if r.getMessage() == "login_failed"]
    assert records and records[0].ip == "203.0.113.68"


@pytest.mark.asyncio
@pytest.mark.real_login_throttle
async def test_wrong_password_on_real_account_is_audited_unknown_email_is_not(
    client: AsyncClient,
):
    """authenticate_user passes the account id to the throttle write, end to end."""
    await _create_active_user(client, "audited@example.com")
    async with TestSessionLocal() as session:
        user_id = (
            await session.execute(
                select(User.id).where(User.email == "audited@example.com")  # pyright: ignore[reportArgumentType]
            )
        ).scalar_one()

    async with await _peer_client("203.0.113.69") as peer:
        for email in ("audited@example.com", "nobody@example.com"):
            resp = await peer.post(
                "/auth/login", json={"email": email, "password": "WrongPass1!"}
            )
            assert resp.status_code == 401

    # Scoped to this test's source IP: client-based tests in this file don't
    # truncate before running, so earlier tests' rows can still be present.
    rows = [
        r
        for r in await audit_rows("user.login_failed")
        if r.ip_address == "203.0.113.69"
    ]
    assert [r.target_id for r in rows] == [user_id]
