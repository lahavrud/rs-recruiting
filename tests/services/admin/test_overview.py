"""Unit tests for the admin overview service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.admin.overview import get_overview


@pytest.mark.asyncio
async def test_get_overview_empty_db(session: AsyncSession):
    """get_overview returns zero counts against an empty database."""
    result = await get_overview(session)

    assert "inbox" in result
    assert "stats" in result
    assert "pulse" in result

    inbox = result["inbox"]
    assert inbox["pending_invites"] == 0
    assert inbox["pending_companies"] == 0
    assert inbox["pending_jobs"] == 0
    assert inbox["new_applications"] == 0
    assert inbox["oldest_pending_company_days"] is None
    assert inbox["oldest_pending_job_days"] is None
    assert inbox["oldest_new_application_days"] is None

    stats = result["stats"]
    assert stats["active_companies"] == 0
    assert stats["published_jobs"] == 0
    assert stats["total_candidates"] == 0
    assert isinstance(stats["application_status_counts"], dict)
    assert isinstance(stats["top_jobs"], list)

    pulse = result["pulse"]
    assert pulse["new_candidates_7d"] == 0
    assert pulse["new_applications_7d"] == 0
    assert isinstance(pulse["recent_items"], list)
    assert isinstance(pulse["trend_30d"], list)
