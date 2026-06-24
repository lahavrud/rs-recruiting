"""Unit tests for the admin candidates service layer."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import ApplicationStatus, JobStatus, UserRole
from src.models import Application, CandidateProfile, CompanyProfile, Job, User
from src.schemas import CandidateProfileUpdate
from src.services.admin.candidates import (
    CANDIDATE_RETENTION_DAYS,
    delete_candidate,
    get_candidate,
    list_candidates,
    purge_expired_candidates,
    update_candidate,
)
from src.services.exceptions import CandidateNotFoundError


@pytest.mark.asyncio
async def test_list_candidates_empty(session: AsyncSession):
    """Returns an empty page when no candidates exist."""
    page = await list_candidates(session)
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_list_candidates_returns_all(
    session: AsyncSession,
    candidate_profile: CandidateProfile,
):
    """Returns all candidates with correct fields when below the page size."""
    page = await list_candidates(session)
    assert len(page.items) == 1
    assert page.items[0].id == candidate_profile.id
    assert page.items[0].email == candidate_profile.email
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_list_candidates_ordered_newest_first(session: AsyncSession):
    """Candidates are returned newest-first within a page."""
    first = CandidateProfile(
        full_name="First", email="first@test.com", phone="050-1111111"
    )
    second = CandidateProfile(
        full_name="Second", email="second@test.com", phone="050-2222222"
    )
    session.add(first)
    session.add(second)
    await session.commit()

    page = await list_candidates(session)
    assert [item.email for item in page.items] == [
        "second@test.com",
        "first@test.com",
    ]


@pytest.mark.asyncio
async def test_list_candidates_paginates_with_cursor(session: AsyncSession):
    """A multi-page traversal returns each candidate exactly once."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(25):
        session.add(
            CandidateProfile(
                full_name=f"User {i:02d}",
                email=f"user{i:02d}@test.com",
                phone="050-0000000",
                created_at=base + timedelta(minutes=i),
            )
        )
    await session.commit()

    seen: list[str] = []
    cursor: str | None = None
    pages = 0
    while True:
        pages += 1
        assert pages <= 5  # safety cap (25 / 10 → 3 pages, generous bound)
        page = await list_candidates(session, cursor=cursor, limit=10)
        seen.extend(item.email for item in page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor

    assert len(seen) == 25
    assert len(set(seen)) == 25  # no duplicates across pages
    # Newest first across the entire traversal
    assert seen[0] == "user24@test.com"
    assert seen[-1] == "user00@test.com"


# ── get_candidate ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_candidate_returns_profile(
    session: AsyncSession, candidate_profile: CandidateProfile
):
    fetched = await get_candidate(candidate_profile.id, session)
    assert fetched.id == candidate_profile.id
    assert fetched.email == candidate_profile.email


@pytest.mark.asyncio
async def test_get_candidate_not_found(session: AsyncSession):
    with pytest.raises(CandidateNotFoundError):
        await get_candidate(99999, session)


# ── update_candidate ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_candidate_partial_keeps_unset_fields(
    session: AsyncSession, candidate_profile: CandidateProfile
):
    updated = await update_candidate(
        candidate_profile.id,
        CandidateProfileUpdate(full_name="New Name"),
        session,
    )
    await session.commit()
    assert updated.full_name == "New Name"
    assert updated.email == candidate_profile.email  # untouched
    assert updated.phone == candidate_profile.phone  # untouched


@pytest.mark.asyncio
async def test_update_candidate_not_found(session: AsyncSession):
    with pytest.raises(CandidateNotFoundError):
        await update_candidate(
            99999, CandidateProfileUpdate(full_name="Anyone"), session
        )


# ── delete_candidate ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_candidate_cascades_applications(
    session: AsyncSession, candidate_profile: CandidateProfile
):
    # Build a published job so we can attach an application
    user = User(
        email="c-deltest@test.com",
        hashed_password="hashed",
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    company = CompanyProfile(
        user_id=user.id,
        name="DelTest Co",
        company_id="123456789",
        contact_email=user.email,
        contact_first_name="א",
        contact_last_name="ב",
        contact_mobile_phone="0501234567",
        address="רח׳ הדוגמה 1, תל אביב",
    )
    session.add(company)
    await session.flush()
    job = Job(
        company_id=company.id,
        title="Role",
        short_description="Short blurb for testing.",
        description="x",
        requirements=[{"text": "x"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="x",
        status=JobStatus.PUBLISHED,
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job)
    await session.flush()
    session.add(
        Application(
            job_id=job.id,
            candidate_id=candidate_profile.id,
            status=ApplicationStatus.NEW,
        )
    )
    await session.commit()

    with patch("src.services.admin.candidates.get_storage_provider") as storage_factory:
        # delete_candidate calls get_storage_provider(); make it return a noop.
        storage_factory.return_value.delete_file = AsyncMock()
        await delete_candidate(candidate_profile.id, session)
        await session.commit()

    candidate_row = await session.execute(
        select(CandidateProfile).where(  # pyright: ignore[reportArgumentType]
            CandidateProfile.id == candidate_profile.id
        )
    )
    assert candidate_row.scalar_one_or_none() is None
    app_row = await session.execute(
        select(Application).where(  # pyright: ignore[reportArgumentType]
            Application.candidate_id == candidate_profile.id
        )
    )
    assert app_row.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_candidate_with_resume_calls_storage(session: AsyncSession):
    candidate = CandidateProfile(
        full_name="Resume Holder",
        email="resume@test.com",
        phone="050-9999999",
        resume_path="resumes/2026/05/abc.pdf",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    with patch("src.services.admin.candidates.get_storage_provider") as storage_factory:
        delete_mock = AsyncMock()
        storage_factory.return_value.delete_file = delete_mock
        await delete_candidate(candidate.id, session)
        await session.commit()
        delete_mock.assert_awaited_once_with("resumes/2026/05/abc.pdf")


@pytest.mark.asyncio
async def test_delete_candidate_not_found(session: AsyncSession):
    with pytest.raises(CandidateNotFoundError):
        await delete_candidate(99999, session)


# ── purge_expired_candidates ──────────────────────────────────────────────────


async def _make_closed_job(
    session: AsyncSession,
    company: CompanyProfile,
    *,
    closed_days_ago: int,
) -> Job:
    job = Job(
        company_id=company.id,
        title="Closed Role",
        short_description="Short blurb for testing.",
        description="x",
        requirements=[{"text": "x"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="x",
        status=JobStatus.CLOSED,
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    job.updated_at = datetime.now(timezone.utc) - timedelta(days=closed_days_ago)
    session.add(job)
    await session.commit()
    return job


async def _make_candidate(
    session: AsyncSession, *, email: str, resume_path: str | None = None
) -> CandidateProfile:
    candidate = CandidateProfile(
        full_name="Test", email=email, phone="050-9999999", resume_path=resume_path
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)
    return candidate


async def _make_app(
    session: AsyncSession,
    *,
    job: Job,
    candidate: CandidateProfile,
    status: ApplicationStatus,
) -> None:
    session.add(Application(job_id=job.id, candidate_id=candidate.id, status=status))
    await session.commit()


@pytest.mark.asyncio
async def test_purge_returns_zero_when_nothing_eligible(session: AsyncSession):
    assert await purge_expired_candidates(session) == 0


@pytest.mark.asyncio
async def test_purge_removes_old_closed_non_hired(
    session: AsyncSession, company_profile: CompanyProfile
):
    job = await _make_closed_job(
        session, company_profile, closed_days_ago=CANDIDATE_RETENTION_DAYS + 30
    )
    candidate = await _make_candidate(
        session, email="purge@test.com", resume_path="uploads/resumes/x.pdf"
    )
    await _make_app(session, job=job, candidate=candidate, status=ApplicationStatus.NEW)

    with patch("src.services.admin.candidates.get_storage_provider") as factory:
        factory.return_value.delete_file = AsyncMock()
        purged = await purge_expired_candidates(session)
        await session.commit()
        factory.return_value.delete_file.assert_awaited_once_with(
            "uploads/resumes/x.pdf"
        )

    assert purged == 1
    remaining = await session.execute(
        select(CandidateProfile).where(CandidateProfile.id == candidate.id)  # pyright: ignore[reportArgumentType]
    )
    assert remaining.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_purge_preserves_hired_candidates(
    session: AsyncSession, company_profile: CompanyProfile
):
    job = await _make_closed_job(
        session, company_profile, closed_days_ago=CANDIDATE_RETENTION_DAYS + 30
    )
    candidate = await _make_candidate(session, email="hired@test.com")
    await _make_app(
        session, job=job, candidate=candidate, status=ApplicationStatus.HIRED
    )

    with patch("src.services.admin.candidates.get_storage_provider") as factory:
        factory.return_value.delete_file = AsyncMock()
        assert await purge_expired_candidates(session) == 0


@pytest.mark.asyncio
async def test_purge_preserves_recently_closed_jobs(
    session: AsyncSession, company_profile: CompanyProfile
):
    job = await _make_closed_job(
        session, company_profile, closed_days_ago=CANDIDATE_RETENTION_DAYS - 30
    )
    candidate = await _make_candidate(session, email="recent@test.com")
    await _make_app(session, job=job, candidate=candidate, status=ApplicationStatus.NEW)

    with patch("src.services.admin.candidates.get_storage_provider") as factory:
        factory.return_value.delete_file = AsyncMock()
        assert await purge_expired_candidates(session) == 0


@pytest.mark.asyncio
async def test_purge_preserves_candidate_with_any_active_application(
    session: AsyncSession, company_profile: CompanyProfile
):
    """Mixed history: one expired application + one active should NOT purge."""
    old_closed = await _make_closed_job(
        session, company_profile, closed_days_ago=CANDIDATE_RETENTION_DAYS + 30
    )
    active = Job(
        company_id=company_profile.id,
        title="Open",
        short_description="Short blurb for testing.",
        description="x",
        requirements=[{"text": "x"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="x",
        status=JobStatus.PUBLISHED,
        salary_min=15000,
        salary_max=25000,
    )
    session.add(active)
    await session.commit()
    await session.refresh(active)

    candidate = await _make_candidate(session, email="mixed@test.com")
    await _make_app(
        session, job=old_closed, candidate=candidate, status=ApplicationStatus.NEW
    )
    await _make_app(
        session, job=active, candidate=candidate, status=ApplicationStatus.NEW
    )

    with patch("src.services.admin.candidates.get_storage_provider") as factory:
        factory.return_value.delete_file = AsyncMock()
        assert await purge_expired_candidates(session) == 0


@pytest.mark.asyncio
async def test_purge_idempotent(session: AsyncSession, company_profile: CompanyProfile):
    """Re-running on a clean state purges nothing."""
    job = await _make_closed_job(
        session, company_profile, closed_days_ago=CANDIDATE_RETENTION_DAYS + 30
    )
    candidate = await _make_candidate(session, email="idem@test.com")
    await _make_app(session, job=job, candidate=candidate, status=ApplicationStatus.NEW)

    with patch("src.services.admin.candidates.get_storage_provider") as factory:
        factory.return_value.delete_file = AsyncMock()
        assert await purge_expired_candidates(session) == 1
        await session.commit()
        assert await purge_expired_candidates(session) == 0


# ---------------------------------------------------------------------------
# get_candidate_job_matches
# ---------------------------------------------------------------------------


def _basis_vec(index: int) -> list[float]:
    """A unit vector along one axis — orthogonal to a different index's vector,
    identical to the same index's vector. Gives predictable cosine distances
    (1.0 and 0.0) without needing a real embedding provider."""
    from src.core.infrastructure.config import settings

    vec = [0.0] * settings.embedding_dim
    vec[index] = 1.0
    return vec


@pytest.mark.asyncio
async def test_get_candidate_job_matches_orders_by_score_desc(
    session: AsyncSession,
    company_profile,
):
    from src.services.admin.candidates import get_candidate_job_matches

    candidate = CandidateProfile(
        full_name="Match", email="match@example.com", embedding=_basis_vec(0)
    )
    session.add(candidate)
    await session.flush()

    def _job(title: str, embedding: list[float]) -> Job:
        return Job(
            company_id=company_profile.id,
            title=title,
            short_description="x",
            description="y",
            requirements=[{"text": "a"}, {"text": "b"}, {"text": "c"}],
            tags=[],
            location="Tel Aviv",
            salary_min=1,
            salary_max=2,
            status=JobStatus.PUBLISHED,
            embedding=embedding,
        )

    # "High" shares the candidate's exact embedding (distance 0 → score 1.0).
    # "Low" is orthogonal to it (distance 1 → score 0.0).
    low, high = _job("Low", _basis_vec(1)), _job("High", _basis_vec(0))
    session.add_all([low, high])
    await session.flush()

    matches = await get_candidate_job_matches(candidate.id, session)
    assert [m.job.title for m in matches] == ["High", "Low"]
    assert matches[0].score == 1.0
    assert matches[1].score == 0.0


@pytest.mark.asyncio
async def test_get_candidate_job_matches_unknown_candidate_raises(
    session: AsyncSession,
):
    from src.services.admin.candidates import get_candidate_job_matches

    with pytest.raises(CandidateNotFoundError):
        await get_candidate_job_matches(999999, session)
