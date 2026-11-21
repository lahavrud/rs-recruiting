"""Unit tests for the admin_company_profiles service layer."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import CompanyProfile
from rs_shared.schemas import CompanyProfileAdminCreate, CompanyProfileAdminUpdate
from rs_shared.services.admin.company_profiles import (
    admin_create_company,
    get_company_profile,
    update_company_profile,
)
from rs_shared.services.exceptions import CompanyNotFoundError


def _admin_create_payload(name: str = "אדמין-קומפ") -> CompanyProfileAdminCreate:
    return CompanyProfileAdminCreate(
        name=name,
        company_id="123456789",
        address="רח׳ אדמין 1, תל אביב",
        contact_email="admin-contact@example.com",
        contact_first_name="אורי",
        contact_last_name="אדמין",
        contact_mobile_phone="0509999999",
    )


@pytest.mark.asyncio
async def test_admin_create_company_persists_profile_without_user(
    session: AsyncSession,
):
    profile = await admin_create_company(_admin_create_payload(), session)
    await session.commit()

    assert profile.id is not None
    assert profile.user_id is None
    assert profile.name == "אדמין-קומפ"
    # Round-trip via the DB to make sure user_id is actually NULL on disk.
    result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.id == profile.id)  # pyright: ignore[reportArgumentType]
    )
    persisted = result.scalar_one()
    assert persisted.user_id is None


@pytest.mark.asyncio
async def test_get_company_profile_returns_admin_created_company(
    session: AsyncSession,
):
    created = await admin_create_company(_admin_create_payload(), session)
    await session.commit()
    fetched = await get_company_profile(created.id, session)
    assert fetched.id == created.id
    assert fetched.user_id is None
    assert fetched.name == created.name


@pytest.mark.asyncio
async def test_get_company_profile_not_found(session: AsyncSession):
    with pytest.raises(CompanyNotFoundError):
        await get_company_profile(99999, session)


@pytest.mark.asyncio
async def test_update_company_profile_partial(session: AsyncSession):
    created = await admin_create_company(_admin_create_payload(), session)
    await session.commit()

    updated = await update_company_profile(
        created.id,
        CompanyProfileAdminUpdate(name="שם חדש", contact_landline_phone="03-1234567"),
        session,
    )
    await session.commit()

    assert updated.name == "שם חדש"
    assert updated.contact_landline_phone == "03-1234567"
    # Untouched fields preserved
    assert updated.company_id == created.company_id
    assert updated.contact_mobile_phone == created.contact_mobile_phone


@pytest.mark.asyncio
async def test_update_company_profile_not_found(session: AsyncSession):
    with pytest.raises(CompanyNotFoundError):
        await update_company_profile(
            99999, CompanyProfileAdminUpdate(name="anything"), session
        )


# ── audit ─────────────────────────────────────────────────────────────────────


async def _audit_rows(session: AsyncSession, action: str) -> list:
    from rs_shared.models import AuditLog

    rows = await session.execute(
        select(AuditLog).where(AuditLog.action == action)  # pyright: ignore[reportArgumentType]
    )
    return list(rows.scalars().all())


@pytest.mark.asyncio
async def test_update_company_profile_audits_changed_field_names(
    session: AsyncSession,
):
    created = await admin_create_company(_admin_create_payload(), session)
    await session.commit()

    await update_company_profile(
        created.id,
        CompanyProfileAdminUpdate(name="שם חדש", address=created.address),
        session,
    )
    await session.commit()

    [row] = await _audit_rows(session, "company.profile_update")
    assert (row.target_type, row.target_id) == ("CompanyProfile", created.id)
    assert row.detail == "fields=name"
    # No user attached, so no login-email event.
    assert await _audit_rows(session, "user.email_change") == []


@pytest.mark.asyncio
async def test_update_company_profile_noop_writes_no_audit(session: AsyncSession):
    created = await admin_create_company(_admin_create_payload(), session)
    await session.commit()

    await update_company_profile(
        created.id, CompanyProfileAdminUpdate(name=created.name), session
    )
    await session.commit()

    assert await _audit_rows(session, "company.profile_update") == []


@pytest.mark.asyncio
async def test_update_company_contact_email_audits_login_email_change(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Changing contact_email on an attached profile changes the login email.

    That is recorded against the user, and neither row carries an address.
    """
    await update_company_profile(
        company_with_user.id,
        CompanyProfileAdminUpdate(contact_email="new-login@example.com"),
        session,
        actor_user_id=4242,
    )
    await session.commit()

    [email_row] = await _audit_rows(session, "user.email_change")
    assert (email_row.target_type, email_row.target_id) == (
        "User",
        company_with_user.user_id,
    )
    assert email_row.actor_user_id == 4242
    assert email_row.detail == "source=admin_company_profile"

    [profile_row] = await _audit_rows(session, "company.profile_update")
    assert profile_row.detail == "fields=contact_email"
    for row in (email_row, profile_row):
        assert "@" not in (row.detail or "")
