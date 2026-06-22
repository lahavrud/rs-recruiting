"""Admin service layer for direct CompanyProfile CRUD.

These functions are addressed by `CompanyProfile.id`, so they work uniformly
for both with-user and admin-created (`user_id=None`) profiles. The
approval/rejection lifecycle that's keyed by `User.id` lives in
`admin_companies.py`.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.models import CompanyProfile
from src.schemas import (
    CompanyProfileAdminCreate,
    CompanyProfileAdminUpdate,
    CompanyProfileRead,
)
from src.services.exceptions import (
    CompanyNotFoundError,
    CompanyNotPendingError,
    EmailAlreadyExistsError,
)


async def get_company_profile(
    profile_id: int, session: AsyncSession
) -> CompanyProfileRead:
    profile = await get_by_id_or_raise(
        session,
        CompanyProfile,
        profile_id,
        lambda pk: CompanyNotFoundError(f"Company profile {pk} not found"),
    )
    return CompanyProfileRead.model_validate(profile)


async def admin_create_company(
    data: CompanyProfileAdminCreate, session: AsyncSession
) -> CompanyProfileRead:
    """Create a CompanyProfile directly, without a user account.

    Used when an admin wants to post jobs against a company that has not
    been onboarded yet. `user_id` is left null; the company can be linked
    to a real user later by extending this flow.
    """
    profile = CompanyProfile(
        user_id=None,
        name=data.name,
        company_id=data.company_id,
        address=data.address,
        contact_email=data.contact_email,
        contact_first_name=data.contact_first_name,
        contact_last_name=data.contact_last_name,
        contact_mobile_phone=data.contact_mobile_phone,
        contact_landline_phone=data.contact_landline_phone,
    )
    session.add(profile)
    await session.flush()
    await session.refresh(profile)
    return CompanyProfileRead.model_validate(profile)


async def delete_orphan_company_profile(profile_id: int, session: AsyncSession) -> None:
    """Delete an admin-created CompanyProfile that has no user account.

    Only deletes profiles with user_id=None (orphan profiles). Raises
    CompanyNotPendingError if the profile is linked to a user, to prevent
    accidental deletion of active or pending company accounts.

    Job and Application rows cascade from companyprofile.id at the DB level
    (migration c4d2a8f1e9b7).

    Raises:
        CompanyNotFoundError: If no profile with that id exists.
        CompanyNotPendingError: If the profile is linked to a user account.
    """
    profile = await get_by_id_or_raise(
        session,
        CompanyProfile,
        profile_id,
        lambda pk: CompanyNotFoundError(f"Company profile {pk} not found"),
    )
    if profile.user_id is not None:
        raise CompanyNotPendingError(
            f"Company profile {profile_id} is linked to user {profile.user_id}; "
            "use the company-user delete endpoint instead"
        )

    await session.delete(profile)
    await session.flush()


async def update_company_profile(
    profile_id: int,
    data: CompanyProfileAdminUpdate,
    session: AsyncSession,
) -> CompanyProfileRead:
    """Apply a partial update to a CompanyProfile.

    Only fields explicitly set on the input schema are updated; unset fields
    leave the existing value untouched.

    Raises:
        CompanyNotFoundError: If no company profile with that id exists.
    """
    result = await session.execute(
        select(CompanyProfile)
        .options(selectinload(CompanyProfile.user))
        .where(CompanyProfile.id == profile_id)  # pyright: ignore[reportArgumentType]
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise CompanyNotFoundError(f"Company profile {profile_id} not found")

    payload = data.model_dump(exclude_unset=True)

    # contact_email is the canonical invariant: when a user is attached, it
    # must equal user.email. So an admin edit that changes contact_email on an
    # attached profile must also update the user's login email atomically.
    new_email = payload.get("contact_email")
    if new_email is not None and profile.user_id is not None:
        new_email = new_email.lower().strip()
        user = profile.user
        if user.email != new_email:
            user.email = new_email
            try:
                await session.flush()
            except IntegrityError as e:
                # user.email has UNIQUE — another account already uses this
                # address. Surface as a domain exception, not a 500.
                raise EmailAlreadyExistsError(new_email) from e

    for field, value in payload.items():
        setattr(profile, field, value)

    await session.flush()
    await session.refresh(profile)
    return CompanyProfileRead.model_validate(profile)
