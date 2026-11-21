"""Tests for the company registration endpoint (POST /auth/register)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from rs_api.main import app
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.security import hash_token, is_password_valid
from rs_shared.enums import InviteTokenStatus
from rs_shared.models import AuditLog, CompanyProfile, InviteToken, User
from rs_shared.services.exceptions import InvalidInviteTokenError
from rs_shared.services.utils.legal import (
    CURRENT_PRIVACY_POLICY_VERSION,
    CURRENT_TERMS_OF_SERVICE_VERSION,
)
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
    from rs_api.api.auth import registration

    registration.limiter.enabled = False

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


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Test successful company registration."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 201

    data = response.json()
    assert data["user"]["email"] == "company@example.com"
    assert data["user"]["role"] == "COMPANY"
    assert data["user"]["is_active"] is False
    assert "password" not in str(data)

    cp = data["company_profile"]
    assert cp["name"] == "Test Company"
    assert cp["company_id"] == "123456789"
    assert cp["contact_first_name"] == "ישראל"
    assert cp["contact_last_name"] == "ישראלי"
    assert cp["contact_mobile_phone"] == "0501234567"
    assert cp["logo_url"] is not None
    assert cp["agreement_signature_url"] is not None
    assert cp["agreement_signed_at"] is not None

    async with TestSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == "company@example.com")  # pyright: ignore[reportArgumentType]
        )
        user = result.scalar_one()
        assert is_password_valid(_STRONG_PASSWORD, user.hashed_password)


@pytest.mark.asyncio
async def test_register_persists_legal_acceptance_metadata(client: AsyncClient):
    """Both acceptances are persisted with version + audit events emitted."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="legal@example.com"),
        files={"logo": FAKE_LOGO_FILE},
        headers={"user-agent": "pytest-ua/1.0"},
    )
    assert response.status_code == 201

    async with TestSessionLocal() as session:
        cp = (
            await session.execute(
                select(CompanyProfile).where(
                    CompanyProfile.contact_email == "legal@example.com"  # pyright: ignore[reportArgumentType]
                )
            )
        ).scalar_one()
        assert cp.privacy_accepted_at is not None
        assert cp.privacy_policy_version == CURRENT_PRIVACY_POLICY_VERSION
        assert cp.terms_accepted_at is not None
        assert cp.terms_version == CURRENT_TERMS_OF_SERVICE_VERSION
        assert cp.acceptance_user_agent == "pytest-ua/1.0"

        actions = {
            row.action
            for row in (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.target_type == "CompanyProfile",  # pyright: ignore[reportArgumentType]
                        AuditLog.target_id == cp.id,  # pyright: ignore[reportArgumentType]
                    )
                )
            )
            .scalars()
            .all()
        }
        assert "company.privacy_accept" in actions
        assert "company.terms_accept" in actions
        assert "company.contract_sign" in actions


@pytest.mark.asyncio
async def test_register_rejects_missing_terms_acceptance(client: AsyncClient):
    """Endpoint returns 422 when the terms-of-service checkbox is false."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="noterms@example.com", terms_accepted="false"),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_company_id(client: AsyncClient):
    """Test 422 when company_id is not 9 digits."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(company_id="12345"),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_mobile_phone(client: AsyncClient):
    """Test 422 when mobile phone is not a valid Israeli mobile number."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(contact_mobile_phone="0521234567890"),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_missing_contact_first_name(client: AsyncClient):
    """Test 422 when contact_first_name is missing."""
    d = _reg_data()
    del d["contact_first_name"]
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=d,
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_missing_logo(client: AsyncClient):
    """Test 422 when logo file is not provided."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Test registration fails when email already exists."""
    await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="duplicate@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email="duplicate@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "email_already_exists"


@pytest.mark.asyncio
async def test_register_missing_token_returns_422(client: AsyncClient):
    """Test registration without a token returns 422."""
    response = await client.post(
        "/auth/register",
        data=_reg_data(),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_token_returns_400(client: AsyncClient):
    """Test that an invalid/expired invite token returns 400."""
    with patch(
        "rs_api.api.auth.registration.validate_invite_token",
        new_callable=AsyncMock,
        side_effect=InvalidInviteTokenError(),
    ):
        response = await client.post(
            "/auth/register",
            params={"token": "expired-or-fake-token"},
            data=_reg_data(email="badtoken@example.com"),
            files={"logo": FAKE_LOGO_FILE},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_token_validated_on_success(client: AsyncClient):
    """Test that the invite token is validated during registration."""
    with patch(
        "rs_api.api.auth.registration.validate_invite_token", new_callable=AsyncMock
    ) as mock_validate:
        response = await client.post(
            "/auth/register",
            params={"token": "one-time-token"},
            data=_reg_data(email="tokenconsumed@example.com"),
            files={"logo": FAKE_LOGO_FILE},
        )
    assert response.status_code == 201
    mock_validate.assert_awaited_once()


# ── invite token, validated for real ─────────────────────────────────────────
# Everything above runs with the suite-wide any-token-is-valid stub. These run
# the endpoint's real validate_invite_token + mark_invite_used against invite
# rows, so dropping either call from the route fails here.


async def _user_count(email: str) -> int:
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(func.count()).select_from(User).where(User.email == email)  # pyright: ignore[reportArgumentType]
        )
        return result.scalar_one()


async def _invite_status(token: str) -> InviteTokenStatus:
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(InviteToken.status).where(
                InviteToken.token_hash == hash_token(token)  # pyright: ignore[reportArgumentType]
            )
        )
        return result.scalar_one()


@pytest.mark.asyncio
@pytest.mark.real_invite_tokens
async def test_register_with_pending_invite_consumes_it(
    client: AsyncClient, make_invite
):
    """A valid invite registers once; the same link is then dead."""
    await make_invite("real-invite")

    first = await client.post(
        "/auth/register",
        params={"token": "real-invite"},
        data=_reg_data(email="first@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert first.status_code == 201
    assert await _invite_status("real-invite") == InviteTokenStatus.USED

    second = await client.post(
        "/auth/register",
        params={"token": "real-invite"},
        data=_reg_data(email="second@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert second.status_code == 400
    assert await _user_count("second@example.com") == 0


@pytest.mark.asyncio
@pytest.mark.real_invite_tokens
@pytest.mark.parametrize(
    "fields",
    [
        pytest.param(None, id="unknown"),
        pytest.param({"status": InviteTokenStatus.REVOKED}, id="revoked"),
        pytest.param(
            {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)},
            id="expired",
        ),
    ],
)
async def test_register_with_unusable_invite_creates_no_user(
    client: AsyncClient, make_invite, fields: dict | None
):
    if fields is not None:
        await make_invite("unusable-invite", **fields)

    response = await client.post(
        "/auth/register",
        params={"token": "unusable-invite"},
        data=_reg_data(email="intruder@example.com"),
        files={"logo": FAKE_LOGO_FILE},
    )

    assert response.status_code == 400
    assert await _user_count("intruder@example.com") == 0


@pytest.mark.asyncio
async def test_register_missing_signature(client: AsyncClient):
    """Test 422 when agreement_signature field is omitted."""
    data = _reg_data()
    del data["agreement_signature"]
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=data,
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_signature(client: AsyncClient):
    """Test 422 when agreement_signature is not valid base64."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(agreement_signature="not-valid-base64!!!"),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_empty_signature(client: AsyncClient):
    """Test 422 when agreement_signature is an empty string."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(agreement_signature=""),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "password",
    [
        "short1!A",
        "Abcdefg1!",
        "UPPERCASE1!abc",
    ],
)
async def test_register_valid_password_complexity(client: AsyncClient, password: str):
    """Test registration succeeds with passwords that meet complexity rules."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(email=f"valid_{len(password)}@example.com", password=password),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "password,reason",
    [
        ("short1!", "too short"),
        ("alllowercase1!", "no uppercase"),
        ("ALLUPPERCASE1!", "no lowercase"),
        ("NoDigitsHere!", "no digit"),
        ("NoSpecialChar1", "no special char"),
    ],
)
async def test_register_weak_password_rejected(
    client: AsyncClient, password: str, reason: str
):
    """Test registration fails when password doesn't meet complexity rules."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(
            email=f"weak_{reason.replace(' ', '_')}@example.com",
            password=password,
        ),
        files={"logo": FAKE_LOGO_FILE},
    )
    assert response.status_code == 422, f"Expected rejection for: {reason}"


@pytest.mark.asyncio
async def test_register_logo_wrong_mime_returns_422(client: AsyncClient):
    """Logo with a non-image/jpeg/png/webp MIME type is rejected with 422."""
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(),
        files={"logo": ("logo.gif", b"GIF89a", "image/gif")},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "unsupported_file_type"


@pytest.mark.asyncio
async def test_register_logo_oversized_returns_413(client: AsyncClient):
    """Logo exceeding 2 MB is rejected with 413."""
    large_logo = b"x" * (3 * 1024 * 1024)  # 3 MB
    response = await client.post(
        "/auth/register",
        params={"token": "valid-test-token"},
        data=_reg_data(),
        files={"logo": ("logo.png", large_logo, "image/png")},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "file_too_large"
