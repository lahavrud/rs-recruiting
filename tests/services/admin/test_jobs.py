"""Unit tests for the admin jobs CRUD service layer."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import ApplicationStatus, JobStatus
from src.models import Application, CandidateProfile, CompanyProfile, Job
from src.schemas import JobAdminCreate, JobAdminUpdate
from src.services.admin.jobs import (
    admin_create_job,
    delete_job,
    list_jobs,
    update_job,
)
from src.services.exceptions import (
    CompanyNotFoundError,
    InvalidCursorError,
    JobNotFoundError,
)


def _payload(company_id: int, title: str = "Backend Engineer") -> JobAdminCreate:
    return JobAdminCreate(
        company_id=company_id,
        title=title,
        short_description="Short blurb for testing.",
        description="ניהול שרתים ופיתוח backend",
        requirements=[{"text": "3+ שנות ניסיון"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="תל אביב",
        salary_min=15000,
        salary_max=22000,
    )


# ── admin_create_job ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_create_job_published_by_default(
    session: AsyncSession, company_with_user: CompanyProfile
):
    job = await admin_create_job(_payload(company_with_user.id), session)
    await session.commit()

    assert job.id is not None
    assert job.status == JobStatus.PUBLISHED
    assert job.company_id == company_with_user.id


@pytest.mark.asyncio
async def test_admin_create_job_unknown_company(session: AsyncSession):
    with pytest.raises(CompanyNotFoundError):
        await admin_create_job(_payload(company_id=99999), session)


# ── update_job ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_job_partial_keeps_unset_fields(
    session: AsyncSession, company_with_user: CompanyProfile
):
    created = await admin_create_job(_payload(company_with_user.id), session)
    await session.commit()

    updated = await update_job(
        created.id,
        JobAdminUpdate(title="Senior Backend Engineer", status=JobStatus.CLOSED),
        session,
    )
    await session.commit()

    assert updated.title == "Senior Backend Engineer"
    assert updated.status == JobStatus.CLOSED
    assert updated.description == created.description  # untouched
    assert updated.location == created.location  # untouched


@pytest.mark.asyncio
async def test_update_job_not_found(session: AsyncSession):
    with pytest.raises(JobNotFoundError):
        await update_job(99999, JobAdminUpdate(title="anything"), session)


_PATCH_EMAIL = "src.services.admin.jobs.enqueue_email_task"
_PATCH_DEFER = "src.services.admin.jobs.defer_after_commit"
# Company-notification emails (closure / generic update) are built in the
# sibling _job_emails module, which holds its own imports of these names.
_PATCH_NOTIFY_EMAIL = "src.services.admin._job_emails.enqueue_email_task"
_PATCH_NOTIFY_DEFER = "src.services.admin._job_emails.defer_after_commit"


@pytest.mark.asyncio
async def test_update_job_enqueues_email_on_real_change(
    session: AsyncSession, company_with_user: CompanyProfile
):
    created = await admin_create_job(_payload(company_with_user.id), session)
    await session.commit()

    with patch(_PATCH_NOTIFY_EMAIL) as mock_email:
        with patch(_PATCH_NOTIFY_DEFER, side_effect=lambda fn: fn()):
            await update_job(
                created.id,
                JobAdminUpdate(title="Updated Title"),
                session,
            )
            await session.commit()

    mock_email.assert_called_once()
    call_kwargs = mock_email.call_args.kwargs
    assert call_kwargs["to"] == company_with_user.contact_email
    assert "עודכן" in call_kwargs["subject"]


@pytest.mark.asyncio
async def test_update_job_no_email_on_noop(
    session: AsyncSession, company_with_user: CompanyProfile
):
    created = await admin_create_job(_payload(company_with_user.id), session)
    await session.commit()

    with patch(_PATCH_NOTIFY_EMAIL) as mock_email:
        with patch(_PATCH_NOTIFY_DEFER, side_effect=lambda fn: fn()):
            await update_job(
                created.id,
                JobAdminUpdate(title="Backend Engineer"),  # same as original
                session,
            )
            await session.commit()

    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_update_job_no_email_when_company_has_no_user(
    session: AsyncSession,
):
    orphan_company = CompanyProfile(
        name="Orphan Co",
        company_id="999",
        address="כתובת",
        contact_email="orphan@test.com",
        contact_first_name="א",
        contact_last_name="ב",
        contact_mobile_phone="0501234567",
    )
    session.add(orphan_company)
    await session.flush()

    created = await admin_create_job(_payload(orphan_company.id), session)
    await session.commit()

    with patch(_PATCH_NOTIFY_EMAIL) as mock_email:
        with patch(_PATCH_NOTIFY_DEFER, side_effect=lambda fn: fn()):
            await update_job(
                created.id,
                JobAdminUpdate(title="New Title"),
                session,
            )
            await session.commit()

    mock_email.assert_not_called()


# ── delete_job ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_job_cascades_applications_keeps_candidate(
    session: AsyncSession, company_with_user: CompanyProfile
):
    job_id = (await admin_create_job(_payload(company_with_user.id), session)).id
    candidate = CandidateProfile(
        full_name="Tester", email="cand@test.com", phone="050-1111111"
    )
    session.add(candidate)
    await session.flush()
    session.add(
        Application(
            job_id=job_id,
            candidate_id=candidate.id,
            status=ApplicationStatus.NEW,
        )
    )
    await session.commit()

    await delete_job(job_id, session)
    await session.commit()

    job_row = await session.execute(
        select(Job).where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    assert job_row.scalar_one_or_none() is None

    app_row = await session.execute(
        select(Application).where(Application.job_id == job_id)  # pyright: ignore[reportArgumentType]
    )
    assert app_row.scalar_one_or_none() is None

    candidate_row = await session.execute(
        select(CandidateProfile).where(CandidateProfile.id == candidate.id)  # pyright: ignore[reportArgumentType]
    )
    assert candidate_row.scalar_one() is not None  # candidate survives


@pytest.mark.asyncio
async def test_delete_job_not_found(session: AsyncSession):
    with pytest.raises(JobNotFoundError):
        await delete_job(99999, session)


# ── close published job ───────────────────────────────────────────────────────


async def _make_application(
    session: AsyncSession,
    job_id: int,
    email: str,
    status: ApplicationStatus = ApplicationStatus.NEW,
) -> Application:
    candidate = CandidateProfile(full_name="מועמד", email=email, phone="050-0000000")
    session.add(candidate)
    await session.flush()
    app = Application(job_id=job_id, candidate_id=candidate.id, status=status)
    session.add(app)
    await session.flush()
    return app


@pytest.mark.asyncio
async def test_close_published_job_sends_company_closure_email(
    session: AsyncSession, company_with_user: CompanyProfile
):
    created = await admin_create_job(_payload(company_with_user.id), session)
    await session.commit()

    with patch(_PATCH_NOTIFY_EMAIL) as mock_email:
        with patch(_PATCH_NOTIFY_DEFER, side_effect=lambda fn: fn()):
            await update_job(
                created.id,
                JobAdminUpdate(status=JobStatus.CLOSED),
                session,
                actor_user_id=1,
            )
            await session.commit()

    assert mock_email.call_count == 1
    kwargs = mock_email.call_args.kwargs
    assert kwargs["to"] == company_with_user.contact_email
    assert "נסגרה" in kwargs["subject"]
    assert "עודכן" not in kwargs["subject"]


@pytest.mark.asyncio
async def test_close_published_job_with_other_changes_sends_two_emails(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Closing AND editing other fields → closure email + generic fields email."""
    created = await admin_create_job(_payload(company_with_user.id), session)
    await session.commit()

    with patch(_PATCH_NOTIFY_EMAIL) as mock_email:
        with patch(_PATCH_NOTIFY_DEFER, side_effect=lambda fn: fn()):
            await update_job(
                created.id,
                JobAdminUpdate(status=JobStatus.CLOSED, title="New Title"),
                session,
            )
            await session.commit()

    subjects = [c.kwargs["subject"] for c in mock_email.call_args_list]
    assert any("נסגרה" in s for s in subjects)
    assert any("עודכן" in s for s in subjects)


@pytest.mark.asyncio
async def test_close_published_job_transitions_active_applications(
    session: AsyncSession, company_with_user: CompanyProfile
):
    job_id = (await admin_create_job(_payload(company_with_user.id), session)).id
    await session.flush()

    app_new = await _make_application(
        session, job_id, "new@test.com", ApplicationStatus.NEW
    )
    app_approved = await _make_application(
        session, job_id, "approved@test.com", ApplicationStatus.APPROVED_BY_ADMIN
    )
    app_rejected = await _make_application(
        session, job_id, "rejected@test.com", ApplicationStatus.REJECTED
    )
    await session.commit()

    with (
        patch(_PATCH_NOTIFY_EMAIL),
        patch(_PATCH_NOTIFY_DEFER, side_effect=lambda fn: fn()),
    ):
        with patch(_PATCH_DEFER, side_effect=lambda fn: fn()):
            await update_job(
                job_id,
                JobAdminUpdate(status=JobStatus.CLOSED),
                session,
            )
            await session.commit()

    await session.refresh(app_new)
    await session.refresh(app_approved)
    await session.refresh(app_rejected)

    assert app_new.status == ApplicationStatus.JOB_CLOSED
    assert app_approved.status == ApplicationStatus.JOB_CLOSED
    assert app_rejected.status == ApplicationStatus.REJECTED  # untouched


@pytest.mark.asyncio
async def test_close_published_job_sends_candidate_emails(
    session: AsyncSession, company_with_user: CompanyProfile
):
    job_id = (await admin_create_job(_payload(company_with_user.id), session)).id
    await session.flush()

    await _make_application(session, job_id, "c1@test.com")
    await _make_application(session, job_id, "c2@test.com")
    await session.commit()

    with (
        patch(_PATCH_NOTIFY_EMAIL),
        patch(_PATCH_NOTIFY_DEFER, side_effect=lambda fn: fn()),
    ):
        with patch(_PATCH_EMAIL) as mock_email:
            with patch(_PATCH_DEFER, side_effect=lambda fn: fn()):
                await update_job(
                    job_id,
                    JobAdminUpdate(status=JobStatus.CLOSED),
                    session,
                )
                await session.commit()

    recipients = {c.kwargs["to"] for c in mock_email.call_args_list}
    assert "c1@test.com" in recipients
    assert "c2@test.com" in recipients


@pytest.mark.asyncio
async def test_close_published_job_records_audit_events(
    session: AsyncSession, company_with_user: CompanyProfile
):
    from src.models import AuditLog

    job_id = (await admin_create_job(_payload(company_with_user.id), session)).id
    await session.flush()

    app1 = await _make_application(session, job_id, "audit1@test.com")
    app2 = await _make_application(session, job_id, "audit2@test.com")
    await session.commit()

    with (
        patch(_PATCH_NOTIFY_EMAIL),
        patch(_PATCH_NOTIFY_DEFER, side_effect=lambda fn: fn()),
    ):
        with patch(_PATCH_DEFER, side_effect=lambda fn: fn()):
            await update_job(
                job_id,
                JobAdminUpdate(status=JobStatus.CLOSED),
                session,
                actor_user_id=42,
            )
            await session.commit()

    rows = list(
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.target_type == "Application",  # pyright: ignore[reportArgumentType]
                    AuditLog.action == "application.status_change",  # pyright: ignore[reportArgumentType]
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    target_ids = {r.target_id for r in rows}
    assert app1.id in target_ids
    assert app2.id in target_ids
    assert all(r.actor_user_id == 42 for r in rows)
    assert all("JOB_CLOSED" in r.detail for r in rows)


@pytest.mark.asyncio
async def test_non_published_to_closed_skips_cascade(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Closing a PENDING_APPROVAL job does not cascade to applications."""
    job = Job(
        company_id=company_with_user.id,
        title="Pending Role",
        short_description="x",
        description="x",
        requirements=[{"text": "x"}, {"text": "y"}, {"text": "z"}],
        location="x",
        status=JobStatus.PENDING_APPROVAL,
        salary_min=10000,
        salary_max=20000,
    )
    session.add(job)
    await session.flush()
    app = await _make_application(session, job.id, "p@test.com")
    await session.commit()

    with (
        patch(_PATCH_NOTIFY_EMAIL),
        patch(_PATCH_NOTIFY_DEFER, side_effect=lambda fn: fn()),
    ):
        with patch(_PATCH_DEFER, side_effect=lambda fn: fn()):
            await update_job(job.id, JobAdminUpdate(status=JobStatus.CLOSED), session)
            await session.commit()

    await session.refresh(app)
    assert (
        app.status == ApplicationStatus.NEW
    )  # cascade only fires on PUBLISHED → CLOSED


# ── list_jobs ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_jobs_filters_by_status(
    session: AsyncSession, company_with_user: CompanyProfile
):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i, status in enumerate(
        [JobStatus.PUBLISHED, JobStatus.PUBLISHED, JobStatus.CLOSED]
    ):
        session.add(
            Job(
                company_id=company_with_user.id,
                title=f"Role {i}",
                short_description="Short blurb for testing.",
                description="x",
                requirements=[{"text": "x"}, {"text": "Req 2"}, {"text": "Req 3"}],
                location="x",
                status=status,
                created_at=base + timedelta(minutes=i),
                salary_min=15000,
                salary_max=25000,
            )
        )
    await session.commit()

    page = await list_jobs(session, status=JobStatus.PUBLISHED)
    assert {item.title for item in page.items} == {"Role 0", "Role 1"}
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_list_jobs_paginates_through_all(
    session: AsyncSession, company_with_user: CompanyProfile
):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(15):
        session.add(
            Job(
                company_id=company_with_user.id,
                title=f"Role {i:02d}",
                short_description="Short blurb for testing.",
                description="x",
                requirements=[{"text": "x"}, {"text": "Req 2"}, {"text": "Req 3"}],
                location="x",
                status=JobStatus.PUBLISHED,
                created_at=base + timedelta(minutes=i),
                salary_min=15000,
                salary_max=25000,
            )
        )
    await session.commit()

    seen: list[str] = []
    cursor: str | None = None
    while True:
        page = await list_jobs(session, cursor=cursor, limit=5)
        seen.extend(item.title for item in page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor

    assert len(seen) == 15
    assert len(set(seen)) == 15
    # newest-first: last-created (Role 14) appears first
    assert seen[0] == "Role 14"
    assert seen[-1] == "Role 00"


@pytest.mark.asyncio
async def test_list_jobs_sort_by_name(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """`sort="name"` orders by title."""
    for title in ["Charlie Role", "Alpha Role", "Bravo Role"]:
        session.add(
            Job(
                company_id=company_with_user.id,
                title=title,
                short_description="Short blurb for testing.",
                description="x",
                requirements=[{"text": "x"}, {"text": "Req 2"}, {"text": "Req 3"}],
                location="x",
                status=JobStatus.PUBLISHED,
                salary_min=15000,
                salary_max=25000,
            )
        )
    await session.commit()

    page = await list_jobs(session, sort="name", order="asc")
    assert [item.title for item in page.items] == [
        "Alpha Role",
        "Bravo Role",
        "Charlie Role",
    ]


@pytest.mark.asyncio
async def test_list_jobs_cursor_rejects_sort_change(
    session: AsyncSession, company_with_user: CompanyProfile
):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(15):
        session.add(
            Job(
                company_id=company_with_user.id,
                title=f"Role {i:02d}",
                short_description="Short blurb for testing.",
                description="x",
                requirements=[{"text": "x"}, {"text": "Req 2"}, {"text": "Req 3"}],
                location="x",
                status=JobStatus.PUBLISHED,
                created_at=base + timedelta(minutes=i),
                salary_min=15000,
                salary_max=25000,
            )
        )
    await session.commit()

    page = await list_jobs(session, limit=10, sort="created_at")
    assert page.next_cursor is not None

    with pytest.raises(InvalidCursorError):
        await list_jobs(session, cursor=page.next_cursor, sort="name")
