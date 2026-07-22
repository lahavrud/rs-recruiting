"""Unit tests for the shared admin list-query predicates."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import CandidateProfile
from rs_shared.services.admin._filters import candidate_not_deleted


@pytest.mark.asyncio
async def test_candidate_not_deleted_matches_only_live_profiles(session: AsyncSession):
    """The predicate keeps live profiles and drops tombstoned ones."""
    session.add(CandidateProfile(full_name="Live One", email="live@test.com"))
    session.add(
        CandidateProfile(
            full_name="[מחוק]",
            email="dead@deleted",
            deleted_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()

    rows = (
        await session.execute(select(CandidateProfile).where(candidate_not_deleted()))
    ).scalars()
    emails = [row.email for row in rows]

    assert "live@test.com" in emails
    assert "dead@deleted" not in emails
