"""Unit tests for the company-registration service.

Carved out of `test_auth.py` to mirror the `auth.py` → `auth_register.py`
service-layer split.
"""

import base64

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import UserRole
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.auth.registration import register_company_user
from src.services.exceptions import EmailAlreadyExistsError
from tests.conftest import FAKE_LOGO
from tests.conftest import FAKE_SIG_B64 as FAKE_SIGNATURE_B64

FAKE_LOGO_NAME = "logo.png"
FAKE_LOGO_TYPE = "image/png"


def _make_user_create(email: str = "company@example.com") -> UserCreate:
    return UserCreate(
        email=email,
        password="SecurePass1!",
        company_profile=CompanyProfileCreate(
            name="Test Company",
            company_id="123456789",
            address="רח׳ הדוגמה 1, תל אביב",
            contact_first_name="ישראל",
            contact_last_name="ישראלי",
            contact_mobile_phone="0501234567",
        ),
    )


@pytest.mark.asyncio
async def test_register_company_user_full_data(session: AsyncSession):
    """Test successful company user registration with all fields."""
    from sqlalchemy import select

    from src.core.infrastructure.security import is_password_valid
    from src.models import CompanyProfile, User

    user_data = _make_user_create()
    result = await register_company_user(
        user_data,
        session,
        FAKE_LOGO,
        FAKE_LOGO_NAME,
        FAKE_LOGO_TYPE,
        FAKE_SIGNATURE_B64,
    )
    await session.commit()

    assert result.user.email == "company@example.com"
    assert result.user.role == UserRole.COMPANY
    assert result.user.is_active is False
    assert result.company_profile.name == "Test Company"
    assert result.company_profile.company_id == "123456789"
    assert result.company_profile.contact_first_name == "ישראל"
    assert result.company_profile.contact_last_name == "ישראלי"
    assert result.company_profile.contact_mobile_phone == "0501234567"
    assert result.company_profile.logo_url is not None

    db_result = await session.execute(
        select(User).where(User.email == "company@example.com")  # pyright: ignore[reportArgumentType]
    )
    db_user = db_result.scalar_one()
    assert is_password_valid("SecurePass1!", db_user.hashed_password)

    db_profile_result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.user_id == db_user.id)  # pyright: ignore[reportArgumentType]
    )
    db_profile = db_profile_result.scalar_one()
    assert db_profile.name == "Test Company"
    assert db_profile.company_id == "123456789"


@pytest.mark.asyncio
async def test_register_company_user_duplicate_email(session: AsyncSession):
    """Test registration fails when email already exists."""
    user_data = _make_user_create("duplicate@example.com")

    await register_company_user(
        user_data,
        session,
        FAKE_LOGO,
        FAKE_LOGO_NAME,
        agreement_signature=FAKE_SIGNATURE_B64,
    )
    await session.commit()

    with pytest.raises(EmailAlreadyExistsError) as exc_info:
        await register_company_user(
            user_data,
            session,
            FAKE_LOGO,
            FAKE_LOGO_NAME,
            agreement_signature=FAKE_SIGNATURE_B64,
        )
    assert "duplicate@example.com" in str(exc_info.value)


@pytest.mark.asyncio
async def test_register_logo_type_rejected(session: AsyncSession):
    """Test registration fails for non-image logo content-type."""
    user_data = _make_user_create("typeerr@example.com")
    with pytest.raises(ValueError, match="image"):
        await register_company_user(
            user_data, session, b"pdf-bytes", "doc.pdf", "application/pdf"
        )


@pytest.mark.asyncio
async def test_register_logo_too_large(session: AsyncSession):
    """Test registration fails when logo exceeds 5 MB."""
    user_data = _make_user_create("toolarge@example.com")
    big_logo = b"x" * (5 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="5 MB"):
        await register_company_user(
            user_data, session, big_logo, "logo.png", "image/png"
        )


@pytest.mark.asyncio
async def test_register_logo_forged_magic_bytes_rejected(session: AsyncSession):
    """Test registration fails when logo bytes don't match declared MIME type."""
    user_data = _make_user_create("forged@example.com")
    exe_bytes = b"MZ" + b"\x00" * 100  # Windows PE header declared as PNG
    with pytest.raises(ValueError, match="content does not match"):
        await register_company_user(
            user_data, session, exe_bytes, "logo.png", "image/png"
        )


@pytest.mark.asyncio
async def test_register_signature_invalid_png_rejected(session: AsyncSession):
    """Test registration fails when signature bytes are not a valid PNG."""
    user_data = _make_user_create("badsig@example.com")
    not_a_png = base64.b64encode(b"not-a-png-just-text").decode()
    with pytest.raises(ValueError, match="PNG"):
        await register_company_user(
            user_data, session, FAKE_LOGO, FAKE_LOGO_NAME, FAKE_LOGO_TYPE, not_a_png
        )
