"""Tests for src/services/companies.py."""

import logging
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CompanyProfile, Job, User
from src.services.company.profile import _resolve_url, export_company_data


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
