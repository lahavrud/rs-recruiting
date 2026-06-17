"""Unit tests for shared admin company-user validation helpers."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import UserRole
from src.models import User
from src.services.admin._helpers import validate_company_user_pending
from src.services.exceptions import CompanyNotFoundError, CompanyNotPendingError


async def _make_user(session: AsyncSession, *, role: UserRole, is_active: bool) -> User:
    user = User(
        email=f"{role.value}-{is_active}@test.com",
        hashed_password="hashed",  # pragma: allowlist secret
        role=role,
        is_active=is_active,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_validate_company_user_pending_returns_pending_company_user(
    session: AsyncSession,
):
    user = await _make_user(session, role=UserRole.COMPANY, is_active=False)

    result = await validate_company_user_pending(user.id, session)

    assert result.id == user.id


@pytest.mark.asyncio
async def test_validate_company_user_pending_raises_when_user_missing(
    session: AsyncSession,
):
    with pytest.raises(CompanyNotFoundError):
        await validate_company_user_pending(99999, session)


@pytest.mark.asyncio
async def test_validate_company_user_pending_raises_when_not_company_role(
    session: AsyncSession,
):
    user = await _make_user(session, role=UserRole.ADMIN, is_active=False)

    with pytest.raises(CompanyNotPendingError):
        await validate_company_user_pending(user.id, session)


@pytest.mark.asyncio
async def test_validate_company_user_pending_raises_when_already_active(
    session: AsyncSession,
):
    user = await _make_user(session, role=UserRole.COMPANY, is_active=True)

    with pytest.raises(CompanyNotPendingError):
        await validate_company_user_pending(user.id, session)
