"""Unit tests for services/utils/recipients.py — notification-recipient lookups."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import get_password_hash
from rs_shared.enums import UserRole
from rs_shared.models import User
from rs_shared.services.utils.recipients import get_all_admin_emails


@pytest.mark.asyncio
async def test_get_all_admin_emails(session: AsyncSession):
    admin1 = User(
        email="admin1@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    admin2 = User(
        email="admin2@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    inactive_admin = User(
        email="admin3@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=False,
    )
    company = User(
        email="company@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add_all([admin1, admin2, inactive_admin, company])
    await session.commit()

    emails = await get_all_admin_emails(session)
    assert set(emails) == {"admin1@example.com", "admin2@example.com"}
