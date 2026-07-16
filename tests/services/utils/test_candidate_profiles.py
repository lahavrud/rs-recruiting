"""Unit tests for services/utils/candidate_profiles.py — lookup + update primitives."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import CandidateProfile
from rs_shared.schemas import CandidateProfileCreate
from rs_shared.services.utils.candidate_profiles import (
    find_candidate_by_email,
    update_candidate_profile,
)


@pytest.mark.asyncio
async def test_find_candidate_by_email_exists(session: AsyncSession):
    candidate = CandidateProfile(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0000",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)
    assert candidate.id is not None

    found = await find_candidate_by_email(email="john@example.com", session=session)

    assert found is not None
    assert found.id == candidate.id
    assert found.email == "john@example.com"


@pytest.mark.asyncio
async def test_find_candidate_by_email_not_exists(session: AsyncSession):
    found = await find_candidate_by_email(
        email="nonexistent@example.com", session=session
    )
    assert found is None


@pytest.mark.asyncio
async def test_update_candidate_profile_updates_full_name_and_fills_unset(
    session: AsyncSession,
):
    candidate = CandidateProfile(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0000",
        linkedin_url=None,
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    new_data = CandidateProfileCreate(
        full_name="John Smith",
        email="john@example.com",
        phone="050-123-4567",
        linkedin_url="https://linkedin.com/in/johndoe",
    )

    updated = await update_candidate_profile(
        candidate=candidate,
        candidate_data=new_data,
        session=session,
    )

    assert updated.full_name == "John Smith"
    # phone is now written through on apply-form updates so the autofill
    # value stays in sync with the most recent submission (Sprint 11 follow-up).
    assert updated.phone == "050-123-4567"
    assert updated.linkedin_url == "https://linkedin.com/in/johndoe"
    assert updated.email == "john@example.com"  # never changes


@pytest.mark.asyncio
async def test_update_candidate_profile_requires_session():
    candidate = CandidateProfile(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0000",
    )
    data = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0000",
    )
    with pytest.raises(ValueError, match="Database session is required"):
        await update_candidate_profile(
            candidate=candidate,
            candidate_data=data,
            session=None,
        )
