"""Shared validation helpers for admin company-user service functions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.enums import UserRole
from src.models import User
from src.services.exceptions import CompanyNotFoundError, CompanyNotPendingError


async def validate_company_user_pending(
    company_user_id: int, session: AsyncSession
) -> User:
    """Fetch a COMPANY user that is pending approval (not yet active).

    Eager-loads `User.company_profile` since callers need it immediately
    after validation.

    Raises:
        CompanyNotFoundError: If no user with that id exists.
        CompanyNotPendingError: If the user is not a COMPANY user, or is
            already active (approved).
    """
    result = await session.execute(
        select(User)
        .options(selectinload(User.company_profile))
        .where(User.id == company_user_id)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one_or_none()
    if not user:
        raise CompanyNotFoundError(f"Company user with ID {company_user_id} not found")
    if user.role != UserRole.COMPANY:
        raise CompanyNotPendingError(
            f"User {company_user_id} is not a COMPANY user (role: {user.role})"
        )
    if user.is_active:
        raise CompanyNotPendingError(
            f"Company user {company_user_id} is already approved (active)"
        )
    return user
