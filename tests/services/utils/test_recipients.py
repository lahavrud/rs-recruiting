"""Unit tests for services/utils/recipients.py — notification-recipient lookups."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import get_password_hash
from rs_shared.enums import UserRole
from rs_shared.models import User
from rs_shared.services.utils.recipients import (
    get_admin_notification_recipients,
    get_all_admin_emails,
)


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


@pytest.mark.asyncio
async def test_admin_notification_recipients_prefers_override(
    session: AsyncSession, monkeypatch
):
    """ADMIN_NOTIFICATION_EMAIL, when set, replaces the per-admin fan-out."""
    from rs_shared.core.infrastructure.config import settings

    monkeypatch.setattr(settings, "admin_notification_email", "ops@rsrecruit.test")
    session.add(
        User(
            email="admin@example.com",
            hashed_password=get_password_hash("password"),
            role=UserRole.ADMIN,
            is_active=True,
        )
    )
    await session.commit()

    assert await get_admin_notification_recipients(session) == ["ops@rsrecruit.test"]


@pytest.mark.asyncio
async def test_admin_notification_recipients_falls_back_to_all_admins(
    session: AsyncSession, monkeypatch
):
    from rs_shared.core.infrastructure.config import settings

    monkeypatch.setattr(settings, "admin_notification_email", None)
    session.add(
        User(
            email="admin@example.com",
            hashed_password=get_password_hash("password"),
            role=UserRole.ADMIN,
            is_active=True,
        )
    )
    await session.commit()

    assert await get_admin_notification_recipients(session) == ["admin@example.com"]
