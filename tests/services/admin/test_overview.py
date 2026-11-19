"""Unit tests for the admin overview service."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import Application, CandidateProfile, Job, User
from rs_shared.services.admin.overview import get_overview


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


@pytest.mark.asyncio
async def test_get_overview_status_counts_keyed_by_enum_value(
    session: AsyncSession, application: Application
):
    """Breakdown is keyed by the enum value, not str(member).

    Regression: str(ApplicationStatus.PENDING_ADMIN_REVIEW) is
    'ApplicationStatus.PENDING_ADMIN_REVIEW', which the frontend's status-keyed
    lookups miss, leaving the breakdown at 0.
    """
    result = await get_overview(session)
    counts = result["stats"]["application_status_counts"]

    assert counts.get("PENDING_ADMIN_REVIEW") == 1
    assert "ApplicationStatus.PENDING_ADMIN_REVIEW" not in counts


@pytest.mark.asyncio
async def test_get_overview_recent_items_all_types_newest_first(
    session: AsyncSession,
    application: Application,
    pending_job: Job,
    company_user: User,
):
    """recent_items merges all three feeds and orders newest-first.

    Covers the UNION ALL branches: a pending-review application, a
    pending-approval job, and a pending (inactive) company must each surface,
    with each type's label/sublabel shape intact.
    """
    result = await get_overview(session)
    items = result["pulse"]["recent_items"]

    assert {item["type"] for item in items} == {"application", "job", "company"}

    stamps = [item["created_at"] for item in items]
    assert stamps == sorted(stamps, reverse=True)

    companies = [i for i in items if i["type"] == "company"]
    jobs = [i for i in items if i["type"] == "job"]
    applications = [i for i in items if i["type"] == "application"]

    assert "Test Company" in {c["label"] for c in companies}
    assert all(c["sublabel"] is None for c in companies)
    assert jobs[0]["label"] == "Senior Python Developer"
    assert jobs[0]["sublabel"] == "Approved Company"  # its company's name
    assert applications[0]["sublabel"] == "Senior Python Developer"  # job title


async def _tombstone(session: AsyncSession, candidate_id: int) -> None:
    candidate = await session.get(CandidateProfile, candidate_id)
    assert candidate is not None
    candidate.deleted_at = datetime.now(timezone.utc)
    await session.flush()


@pytest.mark.asyncio
async def test_get_overview_excludes_tombstoned_candidates(
    session: AsyncSession, application: Application
):
    """Overview counts match the lists, which hide tombstoned candidates.

    Regression: account deletion keeps the candidate's Application rows and
    never moves their status, so a deleted candidate's PENDING_ADMIN_REVIEW
    application stayed in the sidebar badge, the oldest-pending age and the
    recent feed, while /admin/applications (candidate_not_deleted) hid it.
    """
    await _tombstone(session, application.candidate_id)

    result = await get_overview(session)

    assert result["inbox"]["new_applications"] == 0
    assert result["inbox"]["oldest_new_application_days"] is None
    assert result["stats"]["total_candidates"] == 0
    assert result["pulse"]["new_candidates_7d"] == 0
    assert all(i["type"] != "application" for i in result["pulse"]["recent_items"])


@pytest.mark.asyncio
async def test_get_overview_counts_live_candidates(
    session: AsyncSession, application: Application
):
    """The tombstone filter must not drop live candidates."""
    result = await get_overview(session)

    assert result["inbox"]["new_applications"] == 1
    assert result["inbox"]["oldest_new_application_days"] == 0
    assert result["stats"]["total_candidates"] == 1
    assert any(i["type"] == "application" for i in result["pulse"]["recent_items"])
