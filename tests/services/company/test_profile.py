"""Tests for src/services/companies.py."""

import logging
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import CompanyProfile, Job, User
from rs_shared.services.company.profile import _resolve_url, export_company_data


@pytest.mark.asyncio
async def test_resolve_url_returns_none_for_empty_identifier():
    """Empty identifiers should not call storage at all."""
    storage = AsyncMock()
    assert await _resolve_url(storage, None) is None
    assert await _resolve_url(storage, "") is None
    storage.get_file_url.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_url_returns_none_on_storage_failure(caplog):
    """Storage errors should not abort the export, but must be logged."""
    storage = AsyncMock()
    storage.get_file_url.side_effect = RuntimeError("S3 down")

    with caplog.at_level(logging.ERROR):
        assert await _resolve_url(storage, "some/key.pdf") is None

    assert any("Failed to resolve URL" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_export_company_data_includes_jobs(
    session: AsyncSession,
    approved_company_user: User,
    company_profile: CompanyProfile,
    pending_job: Job,
):
    """The export payload includes the company's jobs and presigned URLs."""
    storage = AsyncMock()
    storage.get_file_url.return_value = "https://example/presigned"

    payload = await export_company_data(
        approved_company_user, company_profile, session, storage
    )

    assert payload.user.id == approved_company_user.id
    assert payload.company_profile.id == company_profile.id
    assert any(j.id == pending_job.id for j in payload.jobs)


@pytest.mark.asyncio
async def test_update_company_profile_audits_changed_field_names(
    session: AsyncSession, approved_company_user: User, company_profile: CompanyProfile
):
    from sqlalchemy import select

    from rs_shared.models import AuditLog
    from rs_shared.schemas import CompanyProfileSelfUpdate
    from rs_shared.services.company.profile import update_company_profile

    await update_company_profile(
        company_profile,
        CompanyProfileSelfUpdate(address="רחוב חדש 5", name=company_profile.name),
        session,
        actor_user_id=approved_company_user.id,
        ip_address="203.0.113.4",
    )

    [row] = (
        (
            await session.execute(
                select(AuditLog).where(AuditLog.action == "company.profile_update")  # pyright: ignore[reportArgumentType]
            )
        )
        .scalars()
        .all()
    )
    assert (row.target_type, row.target_id) == ("CompanyProfile", company_profile.id)
    assert row.detail == "fields=address"
    assert row.actor_user_id == approved_company_user.id
