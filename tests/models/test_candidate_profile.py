"""Tests for CandidateProfile model."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.security import get_password_hash
from src.enums import UserRole
from src.models import CandidateProfile, User


@pytest.mark.asyncio
async def test_candidate_profile_creation_persists_all_fields(session: AsyncSession):
    """Test creating a CandidateProfile model."""
    candidate = CandidateProfile(
        full_name="Jane Doe",
        email="jane.doe@example.com",
        phone="+1234567890",
        resume_path="/uploads/resumes/jane_doe.pdf",
        linkedin_url="https://linkedin.com/in/janedoe",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    # Verify candidate was created
    assert candidate.id is not None
    assert candidate.full_name == "Jane Doe"
    assert candidate.email == "jane.doe@example.com"
    assert candidate.created_at is not None


@pytest.mark.asyncio
async def test_candidate_profile_minimal_data(session: AsyncSession):
    """Test creating a candidate with minimal required data."""
    candidate = CandidateProfile(
        full_name="John Smith",
        email="john.smith@example.com",
        phone="050-000-0000",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    assert candidate.id is not None
    assert candidate.full_name == "John Smith"
    assert candidate.phone == "050-000-0000"
    assert candidate.resume_path is None
    assert candidate.linkedin_url is None


@pytest.mark.asyncio
async def test_candidate_profile_unique_email(session: AsyncSession):
    """Test that email must be unique."""
    candidate1 = CandidateProfile(
        full_name="User One",
        email="duplicate@example.com",
        phone="050-000-0000",
    )
    session.add(candidate1)
    await session.commit()

    # Attempting to create another candidate with same email should fail
    candidate2 = CandidateProfile(
        full_name="User Two",
        email="duplicate@example.com",
        phone="050-000-0000",
    )
    session.add(candidate2)

    with pytest.raises(Exception):  # Should raise IntegrityError
        await session.commit()


@pytest.mark.asyncio
async def test_candidate_profile_query_by_email(session: AsyncSession):
    """Test querying candidates by email."""
    candidate = CandidateProfile(
        full_name="Query Test",
        email="query@example.com",
        phone="050-000-0000",
    )
    session.add(candidate)
    await session.commit()

    # Query by email
    result = await session.execute(
        select(CandidateProfile).where(
            CandidateProfile.email == "query@example.com"  # type: ignore[arg-type]
        )
    )
    found_candidate = result.scalar_one()

    assert found_candidate.full_name == "Query Test"
    assert found_candidate.email == "query@example.com"


@pytest.mark.asyncio
async def test_candidate_profile_valid_resume_path(session: AsyncSession):
    """Test that valid paths within uploads/resumes/ are accepted."""
    candidate_data = {
        "full_name": "Valid User",
        "email": "valid@example.com",
        "phone": "050-000-0000",
        "resume_path": "uploads/resumes/valid_resume.pdf",
    }
    candidate = CandidateProfile.model_validate(candidate_data)
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    assert candidate.id is not None
    assert candidate.resume_path == "uploads/resumes/valid_resume.pdf"


@pytest.mark.asyncio
async def test_candidate_profile_none_resume_path_allowed(session: AsyncSession):
    """Test that None is allowed for optional resume_path field."""
    candidate = CandidateProfile(
        full_name="No Resume User",
        email="noresume@example.com",
        resume_path=None,
        phone="050-000-0000",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    assert candidate.id is not None
    assert candidate.resume_path is None


@pytest.mark.asyncio
async def test_candidate_profile_anonymous_lead_has_no_user(session: AsyncSession):
    """Anonymous lead: CandidateProfile created without user_id has user=None.

    Pins the model invariant: `user_id` is nullable, and the back-relationship
    resolves to None for anonymous leads (those who applied via the public
    form without registering).
    """
    lead = CandidateProfile(
        full_name="Anonymous Lead",
        email="lead@example.com",
        phone="050-000-0000",
    )
    session.add(lead)
    await session.commit()

    result = await session.execute(
        select(CandidateProfile)
        .options(selectinload(CandidateProfile.user))
        .where(CandidateProfile.email == "lead@example.com")  # type: ignore[arg-type]
    )
    fetched = result.scalar_one()
    assert fetched.user_id is None
    assert fetched.user is None


@pytest.mark.asyncio
async def test_candidate_profile_linked_to_user(session: AsyncSession):
    """Linked profile: CandidateProfile.user round-trips to its User."""
    user = User(
        email="candidate@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.CANDIDATE,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    profile = CandidateProfile(
        user_id=user.id,  # type: ignore[arg-type]
        full_name="Linked Candidate",
        email="candidate@example.com",
        phone="050-111-2222",
    )
    session.add(profile)
    await session.commit()

    result = await session.execute(
        select(CandidateProfile)
        .options(selectinload(CandidateProfile.user))
        .where(CandidateProfile.email == "candidate@example.com")  # type: ignore[arg-type]
    )
    fetched = result.scalar_one()
    assert fetched.user_id == user.id
    assert fetched.user is not None
    assert fetched.user.email == "candidate@example.com"
    assert fetched.user.role == UserRole.CANDIDATE


@pytest.mark.asyncio
async def test_candidate_profile_user_id_unique(session: AsyncSession):
    """CandidateProfile.user_id has a UNIQUE constraint — two profiles can't
    point at the same User."""
    user = User(
        email="solo@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.CANDIDATE,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    p1 = CandidateProfile(
        user_id=user.id,  # type: ignore[arg-type]
        full_name="First",
        email="solo@example.com",
        phone="050-111-2222",
    )
    session.add(p1)
    await session.commit()

    p2 = CandidateProfile(
        user_id=user.id,  # type: ignore[arg-type]
        full_name="Second",
        email="other@example.com",
        phone="050-333-4444",
    )
    session.add(p2)
    with pytest.raises(Exception):  # IntegrityError on UNIQUE
        await session.commit()


@pytest.mark.asyncio
async def test_delete_user_sets_candidate_profile_user_id_null(
    session: AsyncSession,
):
    """Hard-deleting the linked User must leave the CandidateProfile in place
    with `user_id=None` (FK ON DELETE SET NULL).

    Load-bearing for the Sprint 11 deletion flow (issue #611): we tombstone
    the profile in place rather than cascading the delete, so Application
    rows survive without identifying data.
    """
    user = User(
        email="leaving@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.CANDIDATE,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    profile = CandidateProfile(
        user_id=user.id,  # type: ignore[arg-type]
        full_name="To Be Tombstoned",
        email="leaving@example.com",
        phone="050-555-6666",
    )
    session.add(profile)
    await session.commit()
    profile_id = profile.id

    await session.delete(user)
    await session.commit()

    # Re-query fresh so we see the post-commit state, not a stale identity-map row.
    session.expire_all()
    result = await session.execute(
        select(CandidateProfile).where(
            CandidateProfile.id == profile_id  # type: ignore[arg-type]
        )
    )
    surviving = result.scalar_one_or_none()
    assert surviving is not None, "profile must survive User deletion"
    assert surviving.user_id is None, "FK SET NULL must have nulled user_id"


@pytest.mark.asyncio
async def test_candidate_profile_nested_valid_path(session: AsyncSession):
    """Test that nested paths within uploads/resumes/ are accepted."""
    candidate_data = {
        "full_name": "Nested Path User",
        "email": "nested@example.com",
        "phone": "050-000-0000",
        "resume_path": "uploads/resumes/2026/01/resume.pdf",
    }
    candidate = CandidateProfile.model_validate(candidate_data)
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    assert candidate.id is not None
    assert candidate.resume_path == "uploads/resumes/2026/01/resume.pdf"
