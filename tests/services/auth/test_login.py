"""Tests for src/services/auth/login.py — credential validation and lockout."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import get_password_hash
from src.enums import UserRole
from src.models import User
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.auth.login import authenticate_user
from src.services.auth.registration import (
    CompanyRegistrationData,
    register_company_user,
)
from src.services.exceptions import (
    InvalidCredentialsError,
    PendingApprovalError,
)
from tests.conftest import FAKE_LOGO
from tests.conftest import FAKE_SIG_B64 as FAKE_SIGNATURE_B64

FAKE_LOGO_NAME = "logo.png"


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


def _active_user(email: str = "login-test@example.com") -> User:
    return User(
        email=email,
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_authenticate_user_success(session: AsyncSession):
    """Correct credentials for an active user return the User."""
    user_data = _make_user_create("login@example.com")
    await register_company_user(
        user_data,
        session,
        FAKE_LOGO,
        FAKE_LOGO_NAME,
        CompanyRegistrationData(agreement_signature=FAKE_SIGNATURE_B64),
    )
    await session.commit()

    result = await session.execute(
        select(User).where(User.email == "login@example.com")  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one()
    user.is_active = True
    await session.commit()

    authenticated_user = await authenticate_user(
        "login@example.com", "SecurePass1!", session
    )
    assert authenticated_user.email == "login@example.com"
    assert authenticated_user.is_active is True


@pytest.mark.asyncio
async def test_authenticate_user_invalid_email(session: AsyncSession):
    """Unknown email raises InvalidCredentialsError."""
    with pytest.raises(InvalidCredentialsError):
        await authenticate_user("nonexistent@example.com", "somepassword", session)


@pytest.mark.asyncio
async def test_authenticate_user_invalid_password(session: AsyncSession):
    """Wrong password raises InvalidCredentialsError."""
    user_data = _make_user_create("wrongpass@example.com")
    await register_company_user(
        user_data,
        session,
        FAKE_LOGO,
        FAKE_LOGO_NAME,
        CompanyRegistrationData(agreement_signature=FAKE_SIGNATURE_B64),
    )
    await session.commit()

    result = await session.execute(
        select(User).where(User.email == "wrongpass@example.com")  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one()
    user.is_active = True
    await session.commit()

    with pytest.raises(InvalidCredentialsError):
        await authenticate_user("wrongpass@example.com", "wrongpassword", session)


@pytest.mark.asyncio
async def test_authenticate_user_inactive(session: AsyncSession):
    """Inactive user (pending approval) raises PendingApprovalError."""
    user_data = _make_user_create("inactive@example.com")
    await register_company_user(
        user_data,
        session,
        FAKE_LOGO,
        FAKE_LOGO_NAME,
        CompanyRegistrationData(agreement_signature=FAKE_SIGNATURE_B64),
    )
    await session.commit()

    with pytest.raises(PendingApprovalError):
        await authenticate_user("inactive@example.com", "SecurePass1!", session)
