"""Tests for the daily admin new-applications digest."""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import get_password_hash
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.enums import ApplicationStatus, JobStatus, UserRole
from rs_shared.models import Application, CandidateProfile, EmailOutbox, Job, User
from rs_shared.services.admin.application_digest import (
    DIGEST_KEY_PREFIX,
    JOBS_LIMIT,
    NAMES_PER_JOB,
    send_application_digest,
)

# 06:00 UTC = 08:00 Asia/Jerusalem (winter, UTC+2): the scheduled send time.
NOW = datetime(2026, 11, 20, 6, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _no_outbox_nudge() -> Iterator[None]:
    """Keep the post-commit SQS nudge from sending inline; we assert on rows."""
    with patch(
        "rs_shared.core.tasks.enqueue_send_outbox_email_task", new_callable=AsyncMock
    ):
        yield


@pytest.fixture(autouse=True)
def _all_admins(monkeypatch) -> None:
    from rs_shared.core.infrastructure.config import settings

    monkeypatch.setattr(settings, "admin_notification_email", None)


@pytest.fixture
async def admin(session: AsyncSession) -> User:
    user = User(
        email="admin@test.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _apply(
    session: AsyncSession,
    job: Job,
    name: str,
    created_at: datetime,
    *,
    status: ApplicationStatus = ApplicationStatus.PENDING_ADMIN_REVIEW,
    deleted: bool = False,
) -> Application:
    candidate = CandidateProfile(
        full_name=name,
        email=f"{name.replace(' ', '.').lower()}@example.com",
        deleted_at=created_at if deleted else None,
    )
    session.add(candidate)
    await session.flush()
    application = Application(
        job_id=job.id,  # type: ignore[arg-type]
        candidate_id=candidate.id,  # type: ignore[arg-type]
        status=status,
        created_at=created_at,
    )
    session.add(application)
    await session.flush()
    return application


async def _prior_digest(session: AsyncSession, sent_at: datetime) -> None:
    session.add(
        EmailOutbox(
            dedup_key=f"{DIGEST_KEY_PREFIX}{sent_at.date().isoformat()}",
            to_addrs=["admin@test.com"],
            subject="previous digest",
            body="-",
            created_at=sent_at,
            updated_at=sent_at,
        )
    )
    await session.flush()


async def _run(session: AsyncSession, now: datetime = NOW) -> int:
    async with transactional(session):
        return await send_application_digest(session, now=now)


async def _digests(session: AsyncSession) -> list[EmailOutbox]:
    rows = await session.execute(
        select(EmailOutbox)
        .where(EmailOutbox.dedup_key.like(f"{DIGEST_KEY_PREFIX}%"))  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
        .order_by(EmailOutbox.created_at)  # pyright: ignore[reportArgumentType]
    )
    return list(rows.scalars().all())


@pytest.mark.asyncio
async def test_no_applications_sends_nothing(session: AsyncSession, admin: User):
    """No new applications → no email at all (not an empty digest)."""
    assert await _run(session) == 0
    assert await _digests(session) == []


@pytest.mark.asyncio
async def test_first_digest_covers_the_last_24_hours(
    session: AsyncSession, admin: User, published_job: Job
):
    """With no previous digest, the window falls back to the last 24h."""
    await _apply(session, published_job, "Inside Window", NOW - timedelta(hours=23))
    await _apply(session, published_job, "Too Old", NOW - timedelta(hours=25))

    assert await _run(session) == 1

    [digest] = await _digests(session)
    assert digest.to_addrs == ["admin@test.com"]
    assert digest.dedup_key == f"{DIGEST_KEY_PREFIX}2026-11-20"
    assert "Inside Window" in (digest.html_body or "")
    assert "Too Old" not in (digest.html_body or "")
    assert "Too Old" not in digest.body


@pytest.mark.asyncio
async def test_window_starts_at_the_previous_digest(
    session: AsyncSession, admin: User, published_job: Job
):
    """A missed day catches up: the window runs from the last digest sent."""
    await _prior_digest(session, NOW - timedelta(days=3))
    await _apply(
        session, published_job, "Before Last", NOW - timedelta(days=3, hours=1)
    )
    await _apply(session, published_job, "Two Days Ago", NOW - timedelta(days=2))
    await _apply(session, published_job, "Yesterday", NOW - timedelta(hours=20))

    assert await _run(session) == 2

    digest = (await _digests(session))[-1]
    assert "Two Days Ago" in digest.body
    assert "Yesterday" in digest.body
    assert "Before Last" not in digest.body


@pytest.mark.asyncio
async def test_lookback_is_capped_at_seven_days(
    session: AsyncSession, admin: User, published_job: Job
):
    """A very old previous digest doesn't pull in weeks of history."""
    await _prior_digest(session, NOW - timedelta(days=30))
    await _apply(session, published_job, "Ten Days Ago", NOW - timedelta(days=10))
    await _apply(session, published_job, "Six Days Ago", NOW - timedelta(days=6))

    assert await _run(session) == 1
    digest = (await _digests(session))[-1]
    assert "Six Days Ago" in digest.body
    assert "Ten Days Ago" not in digest.body


@pytest.mark.asyncio
async def test_second_run_on_the_same_day_is_deduped(
    session: AsyncSession, admin: User, published_job: Job
):
    """SQS is at-least-once: a redelivery must not send a second digest."""
    await _apply(session, published_job, "Only Once", NOW - timedelta(hours=2))

    assert await _run(session) == 1
    await _apply(session, published_job, "Late Arrival", NOW + timedelta(minutes=5))
    assert await _run(session, now=NOW + timedelta(minutes=10)) == 0

    assert len(await _digests(session)) == 1


@pytest.mark.asyncio
async def test_tombstoned_candidates_are_left_out(
    session: AsyncSession, admin: User, published_job: Job
):
    """Matches the admin lists and overview (#1162): deleted candidates hidden."""
    await _apply(
        session, published_job, "Deleted Person", NOW - timedelta(hours=3), deleted=True
    )

    assert await _run(session) == 0
    assert await _digests(session) == []


@pytest.mark.asyncio
async def test_groups_by_job_and_truncates_long_lists(
    session: AsyncSession, admin: User, published_job: Job, company_profile
):
    """Busiest job first; past NAMES_PER_JOB names the rest are summarised."""
    quiet_job = Job(
        company_id=company_profile.id,
        title="Quiet Role",
        short_description="-",
        description="-",
        requirements=[],
        tags=[],
        location="Haifa",
        salary_min=1,
        salary_max=2,
        status=published_job.status,
    )
    session.add(quiet_job)
    await session.flush()

    for i in range(NAMES_PER_JOB + 2):
        await _apply(
            session,
            published_job,
            f"Busy Applicant {i:02d}",
            NOW - timedelta(minutes=60 + i),
        )
    await _apply(
        session,
        quiet_job,
        "Quiet Applicant",
        NOW - timedelta(minutes=30),
        status=ApplicationStatus.REJECTED_BY_ADMIN,
    )

    total = NAMES_PER_JOB + 3
    assert await _run(session) == total

    [digest] = await _digests(session)
    html = digest.html_body or ""
    assert str(total) in digest.subject
    assert html.index(published_job.title) < html.index("Quiet Role")
    assert "ועוד 2" in html  # "+2 more" for the busy job
    assert "נדחה" in html  # current status shown in Hebrew
    assert "/admin/applications" in html


@pytest.mark.asyncio
async def test_uses_admin_notification_email_when_set(
    session: AsyncSession, admin: User, published_job: Job, monkeypatch
):
    from rs_shared.core.infrastructure.config import settings

    monkeypatch.setattr(settings, "admin_notification_email", "ops@rsrecruit.test")
    await _apply(session, published_job, "Someone", NOW - timedelta(hours=1))

    await _run(session)

    [digest] = await _digests(session)
    assert digest.to_addrs == ["ops@rsrecruit.test"]


@pytest.mark.asyncio
async def test_no_recipients_sends_nothing(session: AsyncSession, published_job: Job):
    """No admins and no override address: nothing to send to, so no row."""
    await _apply(session, published_job, "Someone", NOW - timedelta(hours=1))

    assert await _run(session) == 0
    assert await _digests(session) == []


@pytest.mark.asyncio
async def test_lists_only_the_busiest_jobs_and_summarises_the_rest(
    session: AsyncSession, admin: User, company_profile
):
    """Past JOBS_LIMIT jobs the rest collapse into one line, so the email stays
    short on a busy day; the total still counts every application."""
    jobs = []
    for i in range(JOBS_LIMIT + 2):
        job = Job(
            company_id=company_profile.id,
            title=f"Role {i}",
            short_description="-",
            description="-",
            requirements=[],
            tags=[],
            location="Tel Aviv",
            salary_min=1,
            salary_max=2,
            status=JobStatus.PUBLISHED,
        )
        session.add(job)
        jobs.append(job)
    await session.flush()
    # Role i gets (7 - i) applications: Role 0 is busiest, and the two
    # quietest (Role 5 with 2, Role 6 with 1) fall past the limit.
    for i, job in enumerate(jobs):
        for n in range(len(jobs) - i):
            await _apply(session, job, f"Applicant {i}-{n}", NOW - timedelta(hours=1))

    total = sum(range(1, len(jobs) + 1))
    assert await _run(session) == total

    [digest] = await _digests(session)
    html = digest.html_body or ""
    for i in range(JOBS_LIMIT):
        assert f"Role {i}" in html
        assert f"Role {i}" in digest.body
    for i in (JOBS_LIMIT, JOBS_LIMIT + 1):
        assert f"Role {i}" not in html
        assert f"Role {i}" not in digest.body
    # Role 5 has 2 applications and Role 6 has 1.
    assert "ועוד 2 משרות עם 3 מועמדויות" in html
    assert "ועוד 2 משרות עם 3 מועמדויות" in digest.body
    assert str(total) in digest.subject


@pytest.mark.asyncio
async def test_no_summary_line_when_jobs_fit(
    session: AsyncSession, admin: User, published_job: Job
):
    await _apply(session, published_job, "Solo", NOW - timedelta(hours=1))

    await _run(session)

    [digest] = await _digests(session)
    assert "משרות עם" not in (digest.html_body or "")
    assert "משרות עם" not in digest.body
