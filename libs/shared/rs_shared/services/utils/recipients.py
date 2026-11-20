"""Notification-recipient lookups shared across service domains.

``get_all_admin_emails`` is a plain ``User`` query with nothing admin-specific;
it lives in the kernel so the auth, company, and public apply flows can each
reach it without importing the ``admin`` domain (see the ``independence``
import-linter contract).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.config import settings
from rs_shared.enums import UserRole
from rs_shared.models import User


async def get_all_admin_emails(session: AsyncSession) -> list[str]:
    """Get email addresses of all active admin users."""
    result = await session.execute(
        select(User.email).where(  # pyright: ignore[reportArgumentType]
            User.role == UserRole.ADMIN,
            User.is_active == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def get_admin_notification_recipients(session: AsyncSession) -> list[str]:
    """Who receives admin notification emails.

    ``ADMIN_NOTIFICATION_EMAIL``, when set, is the single recipient; otherwise
    every active admin. Shared by every admin-facing email that honours the
    override (today: the daily application digest).
    """
    if settings.admin_notification_email:
        return [settings.admin_notification_email]
    return await get_all_admin_emails(session)
