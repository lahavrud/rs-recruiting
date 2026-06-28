"""Unit tests for admin application management service functions."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import ApplicationStatus, JobStatus
from src.models import Application, AuditLog, CandidateProfile, CompanyProfile, Job
from src.schemas import ApplicationRead, ApplicationWithDetails
from src.services.admin.applications import (
    get_application,
    get_application_activity,
    list_applications,
    update_application_notes,
    update_application_status,
)
from src.services.exceptions import ApplicationNotFoundError, InvalidCursorError

# ==================== Helpers ====================


async def _make_application(
    session: AsyncSession,
    company: CompanyProfile,
    candidate: CandidateProfile,
    status: ApplicationStatus = ApplicationStatus.NEW,
    job_status: JobStatus = JobStatus.PUBLISHED,
) -> Application:
    """Helper to create a job + application in the given session."""
    job = Job(
        company_id=company.id,
        title="Test Job",
        short_description="Short blurb for testing.",
        description="Description",
        requirements=[{"text": "Requirements"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="Location",
        status=job_status,
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job)
    await session.flush()

    application = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        status=status,
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)
    return application


async def _make_candidate(
    session: AsyncSession, email: str = "c@test.com"
) -> CandidateProfile:
    """Helper to create a candidate in the given session."""
    candidate = CandidateProfile(
        full_name="Test Candidate",
        email=email,
        phone="050-000-0000",
    )
    session.add(candidate)
    await session.flush()
    return candidate


# ==================== list_applications ====================


@pytest.mark.asyncio
async def test_list_applications_empty(session: AsyncSession):
    """Returns an empty page envelope when no applications exist in this session."""
    page = await list_applications(session)
    # The session fixture is scoped to each test and starts clean; assert the
    # returned items are ApplicationWithDetails instances (or empty list).
    # Do NOT assert len == 0 globally — other test modules may have seeded data
    # that shares the DB between test collection runs.
    assert isinstance(page.items, list)
    assert page.next_cursor is None or isinstance(page.next_cursor, str)


@pytest.mark.asyncio
async def test_list_applications_returns_with_details(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Returns ApplicationWithDetails instances inside the page envelope."""
    candidate = await _make_candidate(session)
    await _make_application(session, company_with_user, candidate)

    page = await list_applications(session)

    assert len(page.items) == 1
    assert isinstance(page.items[0], ApplicationWithDetails)
    assert page.items[0].job is not None
    assert page.items[0].candidate is not None
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_list_applications_filter_by_status(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Filters correctly by application status."""
    candidate = await _make_candidate(session)
    await _make_application(
        session, company_with_user, candidate, status=ApplicationStatus.NEW
    )
    c2 = await _make_candidate(session, email="c2@test.com")
    await _make_application(
        session, company_with_user, c2, status=ApplicationStatus.APPROVED_BY_ADMIN
    )

    new_page = await list_applications(session, status=ApplicationStatus.NEW)
    approved_page = await list_applications(
        session, status=ApplicationStatus.APPROVED_BY_ADMIN
    )

    assert len(new_page.items) == 1
    assert new_page.items[0].status == ApplicationStatus.NEW
    assert len(approved_page.items) == 1
    assert approved_page.items[0].status == ApplicationStatus.APPROVED_BY_ADMIN


@pytest.mark.asyncio
async def test_list_applications_filter_by_job_id(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Filters correctly by job_id."""
    c1 = await _make_candidate(session, email="c1@test.com")
    c2 = await _make_candidate(session, email="c2@test.com")
    app1 = await _make_application(session, company_with_user, c1)
    await _make_application(session, company_with_user, c2)

    page = await list_applications(session, job_id=app1.job_id)

    assert len(page.items) == 1
    assert page.items[0].job_id == app1.job_id


@pytest.mark.asyncio
async def test_list_applications_filter_by_candidate_id(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Filters correctly by candidate_id."""
    c1 = await _make_candidate(session, email="c1@test.com")
    c2 = await _make_candidate(session, email="c2@test.com")
    app1 = await _make_application(session, company_with_user, c1)
    await _make_application(session, company_with_user, c2)

    page = await list_applications(session, candidate_id=c1.id)

    assert len(page.items) == 1
    assert page.items[0].candidate_id == app1.candidate_id


@pytest.mark.asyncio
async def test_list_applications_search_by_candidate_name(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """`q` matches on candidate full_name (case-insensitive substring)."""
    c1 = CandidateProfile(
        full_name="Dina Cohen", email="dina@test.com", phone="050-1111111"
    )
    c2 = CandidateProfile(
        full_name="Yossi Levi", email="yossi@test.com", phone="050-2222222"
    )
    session.add_all([c1, c2])
    await session.flush()
    await _make_application(session, company_with_user, c1)
    await _make_application(session, company_with_user, c2)

    page = await list_applications(session, q="dina")
    assert len(page.items) == 1
    assert page.items[0].candidate.full_name == "Dina Cohen"


@pytest.mark.asyncio
async def test_list_applications_search_by_email(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """`q` matches on candidate email."""
    c1 = CandidateProfile(
        full_name="A", email="unique_addr@example.com", phone="050-1111111"
    )
    c2 = CandidateProfile(full_name="B", email="other@test.com", phone="050-2222222")
    session.add_all([c1, c2])
    await session.flush()
    await _make_application(session, company_with_user, c1)
    await _make_application(session, company_with_user, c2)

    page = await list_applications(session, q="unique_addr")
    assert len(page.items) == 1
    assert page.items[0].candidate.email == "unique_addr@example.com"


@pytest.mark.asyncio
async def test_list_applications_search_by_job_title(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """`q` matches on job title."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)
    await session.refresh(app, ["job"])

    page = await list_applications(session, q="Test Job")
    job_ids = [item.job_id for item in page.items]
    assert app.job_id in job_ids


@pytest.mark.asyncio
async def test_list_applications_search_no_match(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """`q` with no matches returns an empty page."""
    candidate = await _make_candidate(session)
    await _make_application(session, company_with_user, candidate)

    page = await list_applications(session, q="zzz_no_match_xyz")
    assert len(page.items) == 0


@pytest.mark.asyncio
async def test_list_applications_sort_by_name(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """`sort="name"` orders by the applying candidate's full name."""
    bob = CandidateProfile(full_name="Bob", email="bob@test.com", phone="050-1111111")
    alice = CandidateProfile(
        full_name="Alice", email="alice@test.com", phone="050-2222222"
    )
    session.add_all([bob, alice])
    await session.flush()
    await _make_application(session, company_with_user, bob)
    await _make_application(session, company_with_user, alice)

    page = await list_applications(session, sort="name", order="asc")
    assert [item.candidate.full_name for item in page.items] == ["Alice", "Bob"]


@pytest.mark.asyncio
async def test_list_applications_cursor_rejects_sort_change(
    session: AsyncSession, company_with_user: CompanyProfile
):
    for i in range(15):
        candidate = await _make_candidate(session, email=f"c{i:02d}@test.com")
        await _make_application(session, company_with_user, candidate)

    page = await list_applications(session, limit=10, sort="created_at")
    assert page.next_cursor is not None

    with pytest.raises(InvalidCursorError):
        await list_applications(session, cursor=page.next_cursor, sort="name")


async def _make_application_at(
    session: AsyncSession,
    company: CompanyProfile,
    candidate: CandidateProfile,
    created_at: datetime,
    status: ApplicationStatus = ApplicationStatus.NEW,
) -> Application:
    """Like `_make_application`, but pins `created_at` at insert time.

    Setting it after the fact wouldn't reliably stick: the `session` fixture
    uses `expire_on_commit=False`, so an already-loaded ORM object's
    attributes aren't refreshed by a later raw `UPDATE` + commit.
    """
    job = Job(
        company_id=company.id,
        title="Test Job",
        short_description="Short blurb for testing.",
        description="Description",
        requirements=[{"text": "Requirements"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="Location",
        status=JobStatus.PUBLISHED,
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job)
    await session.flush()

    application = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        status=status,
        created_at=created_at,
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)
    return application


@pytest.mark.asyncio
async def test_list_applications_sort_by_status_asc_groups_new_first(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """`sort="status", order="asc"` groups needs-attention statuses before
    terminal ones, regardless of date — an older NEW application still
    outranks a newer JOB_CLOSED one."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    old_new = await _make_candidate(session, email="old-new@test.com")
    await _make_application_at(
        session, company_with_user, old_new, base, status=ApplicationStatus.NEW
    )
    new_closed = await _make_candidate(session, email="new-closed@test.com")
    await _make_application_at(
        session,
        company_with_user,
        new_closed,
        base + timedelta(days=30),
        status=ApplicationStatus.JOB_CLOSED,
    )

    page = await list_applications(session, sort="status", order="asc")
    assert [item.status for item in page.items] == [
        ApplicationStatus.NEW,
        ApplicationStatus.JOB_CLOSED,
    ]


@pytest.mark.asyncio
async def test_list_applications_sort_by_status_desc_reverses_grouping(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """`order="desc"` reverses the whole status grouping (terminal statuses
    first) when there's no secondary column — it does not introduce a date
    tiebreak."""
    new_candidate = await _make_candidate(session, email="new@test.com")
    await _make_application(
        session, company_with_user, new_candidate, status=ApplicationStatus.NEW
    )
    closed_candidate = await _make_candidate(session, email="closed@test.com")
    await _make_application(
        session,
        company_with_user,
        closed_candidate,
        status=ApplicationStatus.JOB_CLOSED,
    )

    page = await list_applications(session, sort="status", order="desc")
    assert [item.status for item in page.items] == [
        ApplicationStatus.JOB_CLOSED,
        ApplicationStatus.NEW,
    ]


@pytest.mark.asyncio
async def test_list_applications_cross_sort_status_then_date(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """`sort="status"` + `sort2="created_at"` groups by status (needs-
    attention first), then orders by date within each group — the cross-sort
    the standalone `sort="status"` deliberately doesn't provide."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    older_new = await _make_candidate(session, email="older-new@test.com")
    await _make_application_at(session, company_with_user, older_new, base)
    newer_new = await _make_candidate(session, email="newer-new@test.com")
    await _make_application_at(
        session, company_with_user, newer_new, base + timedelta(days=1)
    )
    closed = await _make_candidate(session, email="closed@test.com")
    await _make_application_at(
        session,
        company_with_user,
        closed,
        base - timedelta(days=1),  # oldest overall, but a terminal status
        status=ApplicationStatus.JOB_CLOSED,
    )

    page = await list_applications(
        session, sort="status", order="asc", sort2="created_at", order2="desc"
    )
    assert [item.candidate.full_name for item in page.items] == [
        newer_new.full_name,
        older_new.full_name,
        closed.full_name,
    ]


@pytest.mark.asyncio
async def test_list_applications_sort2_equal_to_sort_is_ignored(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """A column can't be paired with itself — `sort2` is silently dropped."""
    candidate = await _make_candidate(session)
    await _make_application(session, company_with_user, candidate)

    page = await list_applications(
        session, sort="status", order="asc", sort2="status", order2="desc"
    )
    assert len(page.items) == 1


@pytest.mark.asyncio
async def test_list_applications_sort_by_status_paginates_across_groups(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """A cursor walk over a status+date cross-sort visits every row exactly
    once, even as it crosses from one status group into the next."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    total_new = 7
    for i in range(total_new):
        candidate = await _make_candidate(session, email=f"new{i:02d}@test.com")
        await _make_application_at(
            session, company_with_user, candidate, base + timedelta(minutes=i)
        )
    closed_candidate = await _make_candidate(session, email="closed@test.com")
    await _make_application_at(
        session,
        company_with_user,
        closed_candidate,
        base + timedelta(days=30),
        status=ApplicationStatus.JOB_CLOSED,
    )

    seen_ids: set[int] = set()
    statuses_seen: list[str] = []
    cursor: str | None = None
    while True:
        page = await list_applications(
            session,
            sort="status",
            order="asc",
            sort2="created_at",
            order2="desc",
            limit=3,
            cursor=cursor,
        )
        seen_ids.update(item.id for item in page.items)
        statuses_seen.extend(item.status for item in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break

    assert len(seen_ids) == total_new + 1
    assert statuses_seen == (
        [ApplicationStatus.NEW] * total_new + [ApplicationStatus.JOB_CLOSED]
    )


@pytest.mark.asyncio
async def test_list_applications_status_sort_cursor_rejects_sort_change(
    session: AsyncSession, company_with_user: CompanyProfile
):
    for i in range(15):
        candidate = await _make_candidate(session, email=f"s{i:02d}@test.com")
        await _make_application(session, company_with_user, candidate)

    page = await list_applications(session, limit=10, sort="created_at")
    assert page.next_cursor is not None

    with pytest.raises(InvalidCursorError):
        await list_applications(session, cursor=page.next_cursor, sort="status")


@pytest.mark.asyncio
async def test_list_applications_cross_sort_cursor_rejects_single_sort_change(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """A cursor minted for the `status`+`created_at` cross-sort must be
    rejected if replayed against plain `status` (no `sort2`) — the cursor
    shapes differ even though the primary `sort` value is identical."""
    for i in range(15):
        candidate = await _make_candidate(session, email=f"x{i:02d}@test.com")
        await _make_application(session, company_with_user, candidate)

    page = await list_applications(session, limit=10, sort="status", sort2="created_at")
    assert page.next_cursor is not None

    with pytest.raises(InvalidCursorError):
        await list_applications(session, cursor=page.next_cursor, sort="status")


# ==================== get_application ====================


@pytest.mark.asyncio
async def test_get_application_success(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Returns ApplicationWithDetails for a valid ID."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    result = await get_application(app.id, session)

    assert isinstance(result, ApplicationWithDetails)
    assert result.id == app.id
    assert result.job is not None
    assert result.candidate is not None
    assert result.candidate.email == candidate.email


@pytest.mark.asyncio
async def test_get_application_not_found(session: AsyncSession):
    """Raises ApplicationNotFoundError for a non-existent ID."""
    with pytest.raises(ApplicationNotFoundError, match="99999"):
        await get_application(99999, session)


# ==================== get_application_activity ====================


@pytest.mark.asyncio
async def test_get_application_activity_not_found(session: AsyncSession):
    """Raises ApplicationNotFoundError for a non-existent ID."""
    with pytest.raises(ApplicationNotFoundError, match="99999"):
        await get_application_activity(99999, session)


@pytest.mark.asyncio
async def test_get_application_activity_returns_own_status_changes(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Returns only this application's status-change rows, newest first."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)
    other_candidate = await _make_candidate(session, email="other@test.com")
    other_app = await _make_application(session, company_with_user, other_candidate)

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    session.add(
        AuditLog(
            action="application.status_change",
            target_type="Application",
            target_id=app.id,
            detail="NEW->APPROVED_BY_ADMIN",
            created_at=base,
        )
    )
    session.add(
        AuditLog(
            action="application.status_change",
            target_type="Application",
            target_id=app.id,
            detail="APPROVED_BY_ADMIN->HIRED",
            created_at=base + timedelta(minutes=1),
        )
    )
    # Another application's status change must not leak into this timeline.
    session.add(
        AuditLog(
            action="application.status_change",
            target_type="Application",
            target_id=other_app.id,
            detail="NEW->REJECTED",
            created_at=base + timedelta(minutes=2),
        )
    )
    await session.commit()

    page = await get_application_activity(app.id, session)

    assert [r.action for r in page.items] == [
        "application.status_change",
        "application.status_change",
        "application.submitted",
    ]
    assert [r.detail for r in page.items] == [
        "APPROVED_BY_ADMIN->HIRED",
        "NEW->APPROVED_BY_ADMIN",
        None,
    ]
    assert page.items[-1].created_at == app.created_at


@pytest.mark.asyncio
async def test_get_application_activity_no_status_changes_yet(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """With no status changes, the synthetic submitted entry anchors the timeline."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    page = await get_application_activity(app.id, session)

    assert len(page.items) == 1
    assert page.items[0].action == "application.submitted"
    assert page.items[0].created_at == app.created_at
    assert page.next_cursor is None


# ==================== update_application_status ====================


@pytest.mark.asyncio
async def test_update_status_new_to_approved(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """NEW → APPROVED_BY_ADMIN is a valid transition."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    result, email_payloads = await update_application_status(
        app.id, ApplicationStatus.APPROVED_BY_ADMIN, session
    )

    assert isinstance(result, ApplicationRead)
    assert result.status == ApplicationStatus.APPROVED_BY_ADMIN
    assert email_payloads == []


@pytest.mark.asyncio
async def test_update_status_new_to_rejected(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """NEW → REJECTED is a valid transition."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    result, _ = await update_application_status(
        app.id, ApplicationStatus.REJECTED, session
    )

    assert result.status == ApplicationStatus.REJECTED


@pytest.mark.asyncio
async def test_update_status_approved_to_hired(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """APPROVED_BY_ADMIN → HIRED is a valid transition."""
    candidate = await _make_candidate(session)
    app = await _make_application(
        session,
        company_with_user,
        candidate,
        status=ApplicationStatus.APPROVED_BY_ADMIN,
    )

    result, _ = await update_application_status(
        app.id, ApplicationStatus.HIRED, session
    )

    assert result.status == ApplicationStatus.HIRED


@pytest.mark.asyncio
async def test_update_status_approved_to_rejected(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """APPROVED_BY_ADMIN → REJECTED is a valid transition."""
    candidate = await _make_candidate(session)
    app = await _make_application(
        session,
        company_with_user,
        candidate,
        status=ApplicationStatus.APPROVED_BY_ADMIN,
    )

    result, _ = await update_application_status(
        app.id, ApplicationStatus.REJECTED, session
    )

    assert result.status == ApplicationStatus.REJECTED


@pytest.mark.asyncio
async def test_update_status_revert_from_rejected(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Admin can revert a REJECTED application — mis-click recovery."""
    candidate = await _make_candidate(session)
    app = await _make_application(
        session, company_with_user, candidate, status=ApplicationStatus.REJECTED
    )

    result, _ = await update_application_status(
        app.id, ApplicationStatus.APPROVED_BY_ADMIN, session
    )
    assert result.status == ApplicationStatus.APPROVED_BY_ADMIN


@pytest.mark.asyncio
async def test_update_status_revert_from_hired(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Admin can revert a HIRED application — mis-click recovery."""
    candidate = await _make_candidate(session)
    app = await _make_application(
        session, company_with_user, candidate, status=ApplicationStatus.HIRED
    )

    result, _ = await update_application_status(
        app.id, ApplicationStatus.REJECTED, session
    )
    assert result.status == ApplicationStatus.REJECTED


@pytest.mark.asyncio
async def test_update_status_skips_intermediate_steps(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Admin can fast-forward NEW → HIRED in one step."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    result, _ = await update_application_status(
        app.id, ApplicationStatus.HIRED, session
    )
    assert result.status == ApplicationStatus.HIRED


@pytest.mark.asyncio
async def test_update_status_with_admin_notes(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Admin notes are persisted on status update."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    result, email_payloads = await update_application_status(
        app.id,
        ApplicationStatus.APPROVED_BY_ADMIN,
        session,
        admin_notes="Strong candidate, schedule interview",
    )

    assert result.admin_notes == "Strong candidate, schedule interview"
    assert email_payloads == []


@pytest.mark.asyncio
async def test_update_status_not_found(session: AsyncSession):
    """Raises ApplicationNotFoundError for a non-existent ID."""
    with pytest.raises(ApplicationNotFoundError):
        await update_application_status(
            99999, ApplicationStatus.APPROVED_BY_ADMIN, session
        )


@pytest.mark.asyncio
async def test_update_status_rejection_email_payload(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Rejecting an application produces one email payload to the candidate."""
    candidate = await _make_candidate(session, email="candidate@test.com")
    app = await _make_application(session, company_with_user, candidate)

    _, email_payloads = await update_application_status(
        app.id, ApplicationStatus.REJECTED, session
    )

    assert len(email_payloads) == 1
    payload = email_payloads[0]
    assert payload["to"] == "candidate@test.com"
    assert "Test Job" in payload["subject"]
    assert "html_body" in payload


@pytest.mark.asyncio
async def test_update_status_rereject_no_email(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Re-rejecting an already-rejected application sends no email."""
    candidate = await _make_candidate(session)
    app = await _make_application(
        session, company_with_user, candidate, status=ApplicationStatus.REJECTED
    )

    _, email_payloads = await update_application_status(
        app.id, ApplicationStatus.REJECTED, session
    )

    assert email_payloads == []


@pytest.mark.asyncio
async def test_update_status_rejection_no_email_for_admin_pushed(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Rejecting an admin-pushed application does not send a rejection email.

    Admin-pushed applications are created without the candidate's knowledge,
    so sending a rejection email referencing their own submission would be
    confusing. The suppression is intentional.
    """
    candidate = await _make_candidate(session, email="pushed@test.com")
    app = await _make_application(session, company_with_user, candidate)
    app.pushed_by_admin_id = 1
    await session.flush()

    _, email_payloads = await update_application_status(
        app.id, ApplicationStatus.REJECTED, session
    )

    assert email_payloads == []


# ==================== update_application_notes ====================


@pytest.mark.asyncio
async def test_update_application_notes_persists_text(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """update_application_notes overwrites admin_notes without changing status."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    result = await update_application_notes(
        app.id, "Looks promising — schedule call.", session
    )
    await session.commit()

    assert isinstance(result, ApplicationRead)
    assert result.admin_notes == "Looks promising — schedule call."
    assert result.status == ApplicationStatus.NEW  # untouched


@pytest.mark.asyncio
async def test_update_application_notes_clears_to_none(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Passing None clears the notes field."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    await update_application_notes(app.id, "first pass", session)
    await session.commit()
    cleared = await update_application_notes(app.id, None, session)
    await session.commit()
    assert cleared.admin_notes is None


@pytest.mark.asyncio
async def test_update_application_notes_not_found(session: AsyncSession):
    with pytest.raises(ApplicationNotFoundError):
        await update_application_notes(99999, "x", session)
