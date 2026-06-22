"""Tests for the company registration endpoint (POST /auth/register)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.core.infrastructure.database import get_session
from src.core.infrastructure.security import is_password_valid
from src.main import app
from src.models import AuditLog, CompanyProfile, User
from src.services.exceptions import InvalidInviteTokenError
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
    from src.api.auth import registration

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
        assert cp.privacy_policy_version == "1.2"
        assert cp.terms_accepted_at is not None
        assert cp.terms_version == "1.1"
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
        "src.api.auth.registration.validate_invite_token",
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
        "src.api.auth.registration.validate_invite_token", new_callable=AsyncMock
    ) as mock_validate:
        response = await client.post(
            "/auth/register",
            params={"token": "one-time-token"},
            data=_reg_data(email="tokenconsumed@example.com"),
            files={"logo": FAKE_LOGO_FILE},
        )
    assert response.status_code == 201
    mock_validate.assert_awaited_once()


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
