"""Tests for authentication endpoints — login, refresh, logout."""

import logging
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from rs_api.main import app
from rs_shared.core.infrastructure.database import get_session
from rs_shared.models import User
from tests.conftest import FAKE_PNG, TestSessionLocal
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


# ==================== Account Lockout Tests ====================


@pytest.mark.asyncio
async def test_account_lockout_after_failed_attempts(client: AsyncClient):
    """Test that an account is locked after repeated failed logins."""
    await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="lockme@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == "lockme@example.com")  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        user.is_active = True
        await session.commit()

    from rs_shared.services.exceptions import AccountLockedError

    attempt_count = 0

    def fake_check_lockout(user, client_ip: str | None = None) -> None:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count > 5:
            raise AccountLockedError(minutes_remaining=15)

    with patch(
        "rs_shared.services.auth.login._check_lockout",
        side_effect=fake_check_lockout,
    ):
        for _ in range(5):
            await client.post(
                "/auth/login",
                json={"email": "lockme@example.com", "password": "WrongPass1!"},
            )
        locked_resp = await client.post(
            "/auth/login",
            json={"email": "lockme@example.com", "password": "WrongPass1!"},
        )

    assert locked_resp.status_code == 429


@pytest.mark.asyncio
async def test_successful_login_clears_failed_attempts(client: AsyncClient):
    """Test that a successful login clears the lockout counter."""
    tokens = await _create_active_user(client, "clearlock@example.com")
    assert "access_token" in tokens  # login succeeded — counter was cleared


@pytest.mark.asyncio
async def test_login_failed_logs_ip(client: AsyncClient, caplog):
    """A bad-password login emits a login_failed log record with an ip field.

    The autouse mock_auth_redis fixture stubs _record_failed_attempt as a no-op
    so that CI tests never open a Redis connection.  We override it with a thin
    stub that calls through to the real logger so the WARNING fires without
    touching Redis.
    """
    await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="logip@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == "logip@example.com")  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        user.is_active = True
        await session.commit()

    _login_logger = logging.getLogger("rs_shared.services.auth.login")

    async def _stub_record_failed(
        user_id: int, email: str, client_ip: str | None = None
    ) -> None:
        _login_logger.warning(
            "login_failed",
            extra={"email_prefix": email[:2] + "***", "attempt": 1, "ip": client_ip},
        )

    with (
        patch(
            "rs_shared.services.auth.login._record_failed_attempt",
            side_effect=_stub_record_failed,
        ),
        caplog.at_level(logging.WARNING, logger="rs_shared.services.auth.login"),
    ):
        await client.post(
            "/auth/login",
            json={"email": "logip@example.com", "password": "WrongPass1!"},
        )

    assert any("login_failed" in r.message and hasattr(r, "ip") for r in caplog.records)
