"""Notification-recipient lookups shared across service domains.

``get_all_admin_emails`` is a plain ``User`` query with nothing admin-specific;
it lives in the kernel so the auth, company, and public apply flows can each
reach it without importing the ``admin`` domain (see the ``independence``
import-linter contract).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
