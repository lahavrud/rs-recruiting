"""Unit tests for the admin candidates service layer."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.enums import ApplicationStatus, JobStatus, UserRole
from rs_shared.models import (
    Application,
    AuditLog,
    CandidateProfile,
    CompanyProfile,
    Job,
    User,
)
from rs_shared.schemas import JobAdminUpdate
from rs_shared.services.admin.candidates import (
    CANDIDATE_RETENTION_DAYS,
    admin_tombstone_candidate,
    get_candidate,
    list_candidate_activity,
    list_candidates,
    purge_expired_candidates,
)
from rs_shared.services.admin.jobs import update_job
from rs_shared.services.exceptions import (
    CandidateAlreadyDeletedError,
    CandidateNotFoundError,
    InvalidCursorError,
)


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


@pytest.mark.asyncio
async def test_list_candidates_sort_by_name_orders_alphabetically(
    session: AsyncSession,
):
    """`sort="name"` orders by full_name, default direction descending."""
    session.add_all(
        [
            CandidateProfile(
                full_name="Alice", email="alice@test.com", phone="050-1111111"
            ),
            CandidateProfile(
                full_name="Bob", email="bob@test.com", phone="050-2222222"
            ),
        ]
    )
    await session.commit()

    page = await list_candidates(session, sort="name")
    assert [item.full_name for item in page.items] == ["Bob", "Alice"]


@pytest.mark.asyncio
async def test_list_candidates_sort_by_name_order_asc(session: AsyncSession):
    """`order="asc"` reverses the direction."""
    session.add_all(
        [
            CandidateProfile(
                full_name="Alice", email="alice@test.com", phone="050-1111111"
            ),
            CandidateProfile(
                full_name="Bob", email="bob@test.com", phone="050-2222222"
            ),
        ]
    )
    await session.commit()

    page = await list_candidates(session, sort="name", order="asc")
    assert [item.full_name for item in page.items] == ["Alice", "Bob"]


@pytest.mark.asyncio
async def test_list_candidates_paginates_with_cursor_sorted_by_name(
    session: AsyncSession,
):
    """A multi-page traversal sorted by name returns each candidate once."""
    names = [f"User{i:02d}" for i in range(25)]
    session.add_all(
        [
            CandidateProfile(
                full_name=name, email=f"{name.lower()}@test.com", phone="050-0000000"
            )
            for name in names
        ]
    )
    await session.commit()

    seen: list[str] = []
    cursor: str | None = None
    pages = 0
    while True:
        pages += 1
        assert pages <= 5
        page = await list_candidates(
            session, cursor=cursor, limit=10, sort="name", order="asc"
        )
        seen.extend(item.full_name for item in page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor

    assert seen == sorted(names)


@pytest.mark.asyncio
async def test_list_candidates_cursor_rejects_sort_change(session: AsyncSession):
    """A cursor minted under one sort can't be replayed against another."""
    session.add_all(
        [
            CandidateProfile(
                full_name=f"User{i:02d}",
                email=f"user{i:02d}@test.com",
                phone="050-0000000",
            )
            for i in range(15)
        ]
    )
    await session.commit()

    page = await list_candidates(session, limit=10, sort="created_at")
    assert page.next_cursor is not None

    with pytest.raises(InvalidCursorError):
        await list_candidates(session, cursor=page.next_cursor, sort="name")


@pytest.mark.asyncio
async def test_list_candidates_filters_by_q_case_insensitive(session: AsyncSession):
    """`q` substring-matches name/email/phone, case-insensitively."""
    session.add_all(
        [
            CandidateProfile(
                full_name="Dana Cohen", email="dana@test.com", phone="0501112233"
            ),
            CandidateProfile(
                full_name="Yossi Levi", email="yossi@test.com", phone="0509998877"
            ),
        ]
    )
    await session.commit()

    page = await list_candidates(session, q="DANA")
    assert [item.email for item in page.items] == ["dana@test.com"]


@pytest.mark.asyncio
async def test_list_candidates_filters_by_q_matches_phone(session: AsyncSession):
    """`q` also matches against the phone column."""
    session.add_all(
        [
            CandidateProfile(
                full_name="Dana Cohen", email="dana@test.com", phone="0501112233"
            ),
            CandidateProfile(
                full_name="Yossi Levi", email="yossi@test.com", phone="0509998877"
            ),
        ]
    )
    await session.commit()

    page = await list_candidates(session, q="9998877")
    assert [item.email for item in page.items] == ["yossi@test.com"]


@pytest.mark.asyncio
async def test_list_candidates_blank_q_returns_all(session: AsyncSession):
    """A blank/whitespace `q` is treated as no filter."""
    session.add(
        CandidateProfile(
            full_name="Dana Cohen", email="dana@test.com", phone="0501112233"
        )
    )
    await session.commit()

    page = await list_candidates(session, q="   ")
    assert len(page.items) == 1


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


# ── list_candidate_activity ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_candidate_activity_not_found(session: AsyncSession):
    with pytest.raises(CandidateNotFoundError):
        await list_candidate_activity(99999, session)


@pytest.mark.asyncio
async def test_list_candidate_activity_merges_candidate_and_application_events(
    session: AsyncSession,
    candidate_profile: CandidateProfile,
    application: Application,
):
    """Audit rows for the candidate and their applications are merged, newest first."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    session.add(
        AuditLog(
            action="candidate.consent",
            target_type="CandidateProfile",
            target_id=candidate_profile.id,
            created_at=base,
        )
    )
    session.add(
        AuditLog(
            action="application.status_change",
            target_type="Application",
            target_id=application.id,
            detail="PENDING_ADMIN_REVIEW->APPROVED_BY_ADMIN",
            created_at=base + timedelta(minutes=1),
        )
    )
    # Unrelated row — different candidate's audit row must not leak in.
    session.add(
        AuditLog(
            action="candidate.delete",
            target_type="CandidateProfile",
            target_id=candidate_profile.id + 999,
            created_at=base + timedelta(minutes=2),
        )
    )
    await session.commit()

    page = await list_candidate_activity(candidate_profile.id, session)
    assert [r.action for r in page.items] == [
        "application.status_change",
        "candidate.consent",
    ]
    assert page.items[0].job_title == "Senior Python Developer"
    assert page.items[1].job_title is None


@pytest.mark.asyncio
async def test_list_candidate_activity_empty(
    session: AsyncSession, candidate_profile: CandidateProfile
):
    page = await list_candidate_activity(candidate_profile.id, session)
    assert page.items == []
    assert page.next_cursor is None


# ── list_candidates — new filter params ─────────────────────────────────────


@pytest.mark.asyncio
async def test_list_candidates_excludes_deleted_by_default(session: AsyncSession):
    """Tombstoned profiles are hidden from the default listing."""
    from datetime import datetime, timezone

    live = CandidateProfile(full_name="Live", email="live@test.com")
    dead = CandidateProfile(
        full_name="[מחוק]",
        email="dead@deleted",
        deleted_at=datetime.now(timezone.utc),
    )
    session.add_all([live, dead])
    await session.commit()

    page = await list_candidates(session)
    emails = [item.email for item in page.items]
    assert "live@test.com" in emails
    assert "dead@deleted" not in emails


@pytest.mark.asyncio
async def test_list_candidates_include_deleted_shows_tombstones(session: AsyncSession):
    """``include_deleted=True`` surfaces tombstoned profiles."""
    from datetime import datetime, timezone

    dead = CandidateProfile(
        full_name="[מחוק]",
        email="shown@deleted",
        deleted_at=datetime.now(timezone.utc),
    )
    session.add(dead)
    await session.commit()

    page = await list_candidates(session, include_deleted=True)
    emails = [item.email for item in page.items]
    assert "shown@deleted" in emails


@pytest.mark.asyncio
async def test_list_candidates_has_account_filter(session: AsyncSession):
    """``has_account=True`` returns only profiles with a linked User."""
    user = User(
        email="linked@test.com",
        hashed_password="hashed",
        role=UserRole.CANDIDATE,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    linked = CandidateProfile(
        user_id=user.id, full_name="Linked", email="linked@test.com"
    )
    anon = CandidateProfile(full_name="Anon", email="anon@test.com")
    session.add_all([linked, anon])
    await session.commit()

    only_linked = await list_candidates(session, has_account=True)
    assert all(item.has_account for item in only_linked.items)
    assert all(item.email == "linked@test.com" for item in only_linked.items)

    only_anon = await list_candidates(session, has_account=False)
    assert all(not item.has_account for item in only_anon.items)
    assert all(item.email == "anon@test.com" for item in only_anon.items)


@pytest.mark.asyncio
async def test_list_candidates_items_include_admin_fields(session: AsyncSession):
    """Response items carry the ``has_account`` / ``is_deleted`` derived fields."""
    session.add(CandidateProfile(full_name="Test", email="admin_fields@test.com"))
    await session.commit()

    page = await list_candidates(session)
    item = next(i for i in page.items if i.email == "admin_fields@test.com")
    assert item.has_account is False
    assert item.is_deleted is False
    assert item.user_email is None


# ── admin_tombstone_candidate ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_tombstone_preserves_profile_row(
    session: AsyncSession, candidate_profile: CandidateProfile
):
    """Tombstone leaves the profile row intact with deleted_at set."""
    storage = MagicMock()
    storage.delete_file = AsyncMock()

    await admin_tombstone_candidate(candidate_profile.id, session, storage=storage)
    await session.flush()

    row = await session.get(CandidateProfile, candidate_profile.id)
    assert row is not None
    assert row.deleted_at is not None
    assert row.full_name == "[מחוק]"


@pytest.mark.asyncio
async def test_admin_tombstone_preserves_applications(
    session: AsyncSession, candidate_profile: CandidateProfile
):
    """Applications are retained (with resume_path NULLed), not cascaded-deleted."""
    user = User(
        email="c-tombtest@test.com",
        hashed_password="hashed",
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    company = CompanyProfile(
        user_id=user.id,
        name="Tomb Co",
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
    app = Application(
        job_id=job.id,
        candidate_id=candidate_profile.id,
        status=ApplicationStatus.PENDING_ADMIN_REVIEW,
        resume_path="resumes/cv.pdf",
    )
    session.add(app)
    await session.commit()
    await session.refresh(app)
    app_id = app.id

    storage = MagicMock()
    storage.delete_file = AsyncMock()
    await admin_tombstone_candidate(candidate_profile.id, session, storage=storage)
    await session.flush()

    app_row = await session.get(Application, app_id)
    assert app_row is not None
    assert app_row.resume_path is None


@pytest.mark.asyncio
async def test_admin_tombstone_with_resume_calls_storage(session: AsyncSession):
    candidate = CandidateProfile(
        full_name="Resume Holder",
        email="resume@test.com",
        phone="050-9999999",
        resume_path="resumes/2026/05/abc.pdf",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    delete_mock = AsyncMock()
    storage = MagicMock()
    storage.delete_file = delete_mock

    await admin_tombstone_candidate(candidate.id, session, storage=storage)
    await session.commit()
    delete_mock.assert_awaited_once_with("resumes/2026/05/abc.pdf")


@pytest.mark.asyncio
async def test_admin_tombstone_not_found(session: AsyncSession):
    storage = MagicMock()
    storage.delete_file = AsyncMock()
    with pytest.raises(CandidateNotFoundError):
        await admin_tombstone_candidate(99999, session, storage=storage)


@pytest.mark.asyncio
async def test_admin_tombstone_already_deleted_raises(session: AsyncSession):
    from datetime import datetime, timezone

    candidate = CandidateProfile(
        full_name="[מחוק]",
        email="already@deleted",
        deleted_at=datetime.now(timezone.utc),
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    storage = MagicMock()
    storage.delete_file = AsyncMock()
    with pytest.raises(CandidateAlreadyDeletedError):
        await admin_tombstone_candidate(candidate.id, session, storage=storage)


async def _make_registered_candidate(
    session: AsyncSession, *, email: str
) -> tuple[User, CandidateProfile]:
    """Create a User(role=CANDIDATE) linked 1:1 to a CandidateProfile."""
    user = User(
        email=email,
        hashed_password="hashed",
        role=UserRole.CANDIDATE,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    candidate = CandidateProfile(
        user_id=user.id, full_name="Reg Candidate", email=email, phone="050-9999999"
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(user)
    await session.refresh(candidate)
    return user, candidate


@pytest.mark.asyncio
async def test_admin_tombstone_removes_backing_user(session: AsyncSession):
    user, candidate = await _make_registered_candidate(
        session, email="registered@test.com"
    )
    user_id = user.id

    with patch(
        "rs_shared.services.admin.candidates.get_storage_provider"
    ) as storage_factory:
        storage_factory.return_value.delete_file = AsyncMock()
        await admin_tombstone_candidate(candidate.id, session)
        await session.commit()

    user_row = await session.execute(
        select(User).where(User.id == user_id)  # pyright: ignore[reportArgumentType]
    )
    assert user_row.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_admin_tombstone_frees_email_for_reregistration(session: AsyncSession):
    _, candidate = await _make_registered_candidate(session, email="reuse@test.com")

    with patch(
        "rs_shared.services.admin.candidates.get_storage_provider"
    ) as storage_factory:
        storage_factory.return_value.delete_file = AsyncMock()
        await admin_tombstone_candidate(candidate.id, session)
        await session.commit()

    # No orphaned User / CandidateProfile holds the unique email hostage.
    session.add(
        User(
            email="reuse@test.com",
            hashed_password="hashed",
            role=UserRole.CANDIDATE,
            is_active=True,
        )
    )
    await session.commit()  # would raise IntegrityError if the email were taken


@pytest.mark.asyncio
async def test_admin_tombstone_anonymous_lead_tombstoned(session: AsyncSession):
    """A lead with user_id=None tombstones cleanly (no backing User to remove)."""
    candidate = await _make_candidate(session, email="lead@test.com")

    with patch(
        "rs_shared.services.admin.candidates.get_storage_provider"
    ) as storage_factory:
        storage_factory.return_value.delete_file = AsyncMock()
        await admin_tombstone_candidate(candidate.id, session)
        await session.commit()

    # The profile row is retained (tombstoned), not hard-deleted.
    row = await session.get(CandidateProfile, candidate.id)
    assert row is not None
    assert row.deleted_at is not None
    assert row.full_name == "[מחוק]"


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
    # Retention is anchored on closed_at. updated_at is deliberately left at
    # "now" so these fixtures also prove a recent edit does not hold the
    # candidate back from purge.
    job.closed_at = datetime.now(timezone.utc) - timedelta(days=closed_days_ago)
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
    # JOB_CLOSED is the realistic post-cascade state for an application on a
    # closed job. An *active* status here would preserve the candidate — see
    # test_purge_preserves_active_application_on_long_closed_job.
    await _make_app(
        session,
        job=job,
        candidate=candidate,
        status=ApplicationStatus.JOB_CLOSED,
    )

    with patch(
        "rs_shared.services.admin._candidates_purge.get_storage_provider"
    ) as factory:
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

    with patch(
        "rs_shared.services.admin._candidates_purge.get_storage_provider"
    ) as factory:
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
    # Terminal, so recency of the close is the only thing preserving here.
    await _make_app(
        session,
        job=job,
        candidate=candidate,
        status=ApplicationStatus.JOB_CLOSED,
    )

    with patch(
        "rs_shared.services.admin._candidates_purge.get_storage_provider"
    ) as factory:
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
    # Expired history on the closed job, still in flight on the open one.
    await _make_app(
        session,
        job=old_closed,
        candidate=candidate,
        status=ApplicationStatus.JOB_CLOSED,
    )
    await _make_app(
        session,
        job=active,
        candidate=candidate,
        status=ApplicationStatus.PENDING_ADMIN_REVIEW,
    )

    with patch(
        "rs_shared.services.admin._candidates_purge.get_storage_provider"
    ) as factory:
        factory.return_value.delete_file = AsyncMock()
        assert await purge_expired_candidates(session) == 0


@pytest.mark.asyncio
async def test_purge_idempotent(session: AsyncSession, company_profile: CompanyProfile):
    """Re-running on a clean state purges nothing."""
    job = await _make_closed_job(
        session, company_profile, closed_days_ago=CANDIDATE_RETENTION_DAYS + 30
    )
    candidate = await _make_candidate(session, email="idem@test.com")
    await _make_app(
        session,
        job=job,
        candidate=candidate,
        status=ApplicationStatus.JOB_CLOSED,
    )

    with patch(
        "rs_shared.services.admin._candidates_purge.get_storage_provider"
    ) as factory:
        factory.return_value.delete_file = AsyncMock()
        assert await purge_expired_candidates(session) == 1
        await session.commit()
        assert await purge_expired_candidates(session) == 0


@pytest.mark.asyncio
async def test_purge_removes_backing_user(
    session: AsyncSession, company_profile: CompanyProfile
):
    """A purged registered candidate leaves no orphaned User behind."""
    job = await _make_closed_job(
        session, company_profile, closed_days_ago=CANDIDATE_RETENTION_DAYS + 30
    )
    user, candidate = await _make_registered_candidate(
        session, email="purge-user@test.com"
    )
    user_id = user.id
    await _make_app(
        session,
        job=job,
        candidate=candidate,
        status=ApplicationStatus.JOB_CLOSED,
    )

    with patch(
        "rs_shared.services.admin._candidates_purge.get_storage_provider"
    ) as factory:
        factory.return_value.delete_file = AsyncMock()
        assert await purge_expired_candidates(session) == 1
        await session.commit()

    user_row = await session.execute(
        select(User).where(User.id == user_id)  # pyright: ignore[reportArgumentType]
    )
    assert user_row.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_purge_unaffected_by_edit_to_long_closed_job(
    session: AsyncSession, company_profile: CompanyProfile
):
    """Editing a closed job must not restart its candidates' retention clock.

    Retention is anchored on closed_at; updated_at moves on every edit, so
    keying off it let any later touch of a closed job silently re-retain
    everyone who had applied to it.
    """
    job = await _make_closed_job(
        session, company_profile, closed_days_ago=CANDIDATE_RETENTION_DAYS + 30
    )
    candidate = await _make_candidate(session, email="edited@test.com")
    await _make_app(
        session,
        job=job,
        candidate=candidate,
        status=ApplicationStatus.JOB_CLOSED,
    )

    # An admin fixes a typo on the long-closed job today.
    await update_job(job.id, JobAdminUpdate(title="Corrected Title"), session)
    await session.commit()

    await session.refresh(job)
    assert job.updated_at >= datetime.now(timezone.utc) - timedelta(minutes=5)

    with patch(
        "rs_shared.services.admin._candidates_purge.get_storage_provider"
    ) as factory:
        factory.return_value.delete_file = AsyncMock()
        assert await purge_expired_candidates(session) == 1


@pytest.mark.asyncio
async def test_purge_preserves_closed_job_with_null_closed_at(
    session: AsyncSession, company_profile: CompanyProfile
):
    """An unknown close date preserves — over-retaining is the safe reading."""
    job = await _make_closed_job(
        session, company_profile, closed_days_ago=CANDIDATE_RETENTION_DAYS + 30
    )
    job.closed_at = None
    session.add(job)
    await session.commit()

    candidate = await _make_candidate(session, email="nullclosed@test.com")
    # Terminal, so the NULL anchor is the only thing preserving here.
    await _make_app(
        session,
        job=job,
        candidate=candidate,
        status=ApplicationStatus.JOB_CLOSED,
    )

    with patch(
        "rs_shared.services.admin._candidates_purge.get_storage_provider"
    ) as factory:
        factory.return_value.delete_file = AsyncMock()
        assert await purge_expired_candidates(session) == 0


@pytest.mark.parametrize(
    "status",
    [s for s in ApplicationStatus if s.is_active],
)
@pytest.mark.asyncio
async def test_purge_preserves_active_application_on_long_closed_job(
    session: AsyncSession,
    company_profile: CompanyProfile,
    status: ApplicationStatus,
):
    """An in-flight application preserves regardless of the job's age or status.

    The preserve rule used to infer "still active" from ``Job.status != CLOSED``
    rather than reading the application's own status, so an application left in
    flight on a long-closed job did not hold its candidate back — the candidate
    was purged while the pipeline still showed the application as live work.
    """
    job = await _make_closed_job(
        session, company_profile, closed_days_ago=CANDIDATE_RETENTION_DAYS + 30
    )
    candidate = await _make_candidate(session, email=f"active-{status.value}@test.com")
    await _make_app(session, job=job, candidate=candidate, status=status)

    with patch(
        "rs_shared.services.admin._candidates_purge.get_storage_provider"
    ) as factory:
        factory.return_value.delete_file = AsyncMock()
        assert await purge_expired_candidates(session) == 0

    remaining = await session.execute(
        select(CandidateProfile).where(CandidateProfile.id == candidate.id)  # pyright: ignore[reportArgumentType]
    )
    assert remaining.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# get_candidate_job_matches
# ---------------------------------------------------------------------------


def _basis_vec(index: int) -> list[float]:
    """A unit vector along one axis — orthogonal to a different index's vector,
    identical to the same index's vector. Gives predictable cosine distances
    (1.0 and 0.0) without needing a real embedding provider."""
    from rs_shared.core.infrastructure.config import settings

    vec = [0.0] * settings.embedding_dim
    vec[index] = 1.0
    return vec


@pytest.mark.asyncio
async def test_get_candidate_job_matches_orders_by_score_desc(
    session: AsyncSession,
    company_profile,
):
    from rs_shared.services.admin.candidates import get_candidate_job_matches

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
    from rs_shared.services.admin.candidates import get_candidate_job_matches

    with pytest.raises(CandidateNotFoundError):
        await get_candidate_job_matches(999999, session)
