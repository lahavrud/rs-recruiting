"""Tests for Job model."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.enums import JobStatus
from rs_shared.models import CompanyProfile, Job


@pytest.mark.asyncio
async def test_job_creation_with_defaults_sets_pending_approval_status(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Test creating a Job model."""
    assert company_with_user.id is not None
    job = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        short_description="Short blurb for testing.",
        description="We are looking for a senior Python developer...",
        requirements=[
            {"text": "5+ years experience with Python, FastAPI, PostgreSQL"},
            {"text": "Req 2"},
            {"text": "Req 3"},
        ],
        location="Tel Aviv, Israel",
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Verify job was created with correct defaults
    assert job.id is not None
    assert job.title == "Senior Python Developer"
    assert job.status == JobStatus.PENDING_APPROVAL
    assert job.created_at is not None
    assert job.updated_at is not None


@pytest.mark.asyncio
async def test_job_required_fields(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Test that all required fields must be provided."""
    assert company_with_user.id is not None
    # Missing title should fail at Pydantic validation
    with pytest.raises(Exception):  # ValidationError from Pydantic
        job = Job(  # type: ignore[call-arg]
            company_id=company_with_user.id,
            # title is missing - should fail
            description="Description",
            requirements=[
                {"text": "Requirements"},
                {"text": "Req 2"},
                {"text": "Req 3"},
            ],
            location="Location",
        )
        session.add(job)
        await session.commit()


@pytest.mark.asyncio
async def test_job_salary_range_db_constraint_rejects_inverted(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """DB-level CHECK rejects salary_min > salary_max even when bypassing Pydantic."""
    assert company_with_user.id is not None
    job = Job(
        company_id=company_with_user.id,
        title="Test Job",
        short_description="Short blurb for testing.",
        description="d",
        requirements=[{"text": "r"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="l",
        salary_min=20000,
        salary_max=10000,
    )
    session.add(job)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_job_salary_range_db_rejects_null(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """NULL salary_min or salary_max is rejected at the DB level (NOT NULL)."""
    assert company_with_user.id is not None
    job = Job(
        company_id=company_with_user.id,
        title="Test Job",
        short_description="Short blurb for testing.",
        description="d",
        requirements=[{"text": "r"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="l",
        salary_min=15000,
        salary_max=None,  # type: ignore[arg-type]
    )
    session.add(job)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_job_salary_range_db_constraint_allows_equal(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """salary_min == salary_max is allowed (boundary case)."""
    assert company_with_user.id is not None
    job = Job(
        company_id=company_with_user.id,
        title="Test Job",
        short_description="Short blurb for testing.",
        description="d",
        requirements=[{"text": "r"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="l",
        salary_min=15000,
        salary_max=15000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None


# ── closed_at retention anchor ────────────────────────────────────────────────
#
# The anchor is maintained by a database trigger, mirrored onto in-memory
# objects by the mapper-level hooks in models/jobs.py. These tests drive both
# paths: ORM writes exercise the mirror and the trigger together, Core-level
# UPDATEs bypass the mirror entirely and leave only the trigger.


@pytest.mark.asyncio
async def test_closed_at_stamped_on_raw_status_assignment(
    session: AsyncSession,
    company_with_user: CompanyProfile,
    make_job,
):
    """The anchor is maintained by the model, not by the service that closes.

    This is the whole point of enforcing it below the services: a close without
    going through update_job/reject_job — a script, a shell, a future code path
    — still gets a retention anchor. Without one the purge preserves the job's
    candidates forever.
    """
    job = make_job(company_with_user.id, JobStatus.PUBLISHED)
    session.add(job)
    await session.commit()
    assert job.closed_at is None

    job.status = JobStatus.CLOSED
    await session.commit()

    await session.refresh(job)
    assert job.closed_at is not None


@pytest.mark.asyncio
async def test_closed_at_stamped_when_created_closed(
    session: AsyncSession,
    company_with_user: CompanyProfile,
    make_job,
):
    """A job born CLOSED — as the seed script and admin create both allow."""
    job = make_job(company_with_user.id, JobStatus.CLOSED)
    session.add(job)
    await session.commit()

    await session.refresh(job)
    assert job.closed_at is not None


@pytest.mark.asyncio
async def test_closed_at_untouched_by_unrelated_edit(
    session: AsyncSession,
    company_with_user: CompanyProfile,
    make_job,
):
    """An edit that does not move the status must not move the anchor."""
    job = make_job(company_with_user.id, JobStatus.CLOSED)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    anchor = job.closed_at

    job.title = "Renamed"
    await session.commit()

    await session.refresh(job)
    assert job.closed_at == anchor


@pytest.mark.asyncio
async def test_closed_at_cleared_on_reopen(
    session: AsyncSession,
    company_with_user: CompanyProfile,
    make_job,
):
    """A stale anchor must not outlive the CLOSED status."""
    job = make_job(company_with_user.id, JobStatus.CLOSED)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.closed_at is not None

    job.status = JobStatus.PUBLISHED
    await session.commit()

    await session.refresh(job)
    assert job.closed_at is None


@pytest.mark.asyncio
async def test_closed_at_readable_without_refresh(
    session: AsyncSession,
    company_with_user: CompanyProfile,
    make_job,
):
    """The mirror's whole reason to exist, pinned.

    Both session factories use ``expire_on_commit=False``, so attributes are not
    reloaded after commit. If only the trigger stamped the anchor, a caller
    reading ``job.closed_at`` straight after closing would see the pre-write
    value with nothing to hint it is stale.
    """
    job = make_job(company_with_user.id, JobStatus.PUBLISHED)
    session.add(job)
    await session.commit()

    job.status = JobStatus.CLOSED
    await session.commit()

    assert job.closed_at is not None  # deliberately no refresh

    job.status = JobStatus.PUBLISHED
    await session.commit()

    assert job.closed_at is None  # cleared in memory too


@pytest.mark.asyncio
async def test_orm_and_trigger_agree_on_a_caller_supplied_anchor(
    session: AsyncSession,
    company_with_user: CompanyProfile,
    make_job,
):
    """Closing with an explicit anchor keeps it, whichever layer handles it.

    The trigger only ever fills a NULL. The ORM mirror has to match, or a data
    correction replaying a historical close would get ``now()`` through the ORM
    and its own value through a bulk UPDATE — the same write, two answers.
    """
    backdated = datetime.now(timezone.utc) - timedelta(days=200)

    via_orm = make_job(company_with_user.id, JobStatus.PUBLISHED)
    via_bulk = make_job(company_with_user.id, JobStatus.PUBLISHED)
    session.add_all([via_orm, via_bulk])
    await session.commit()

    via_orm.status = JobStatus.CLOSED
    via_orm.closed_at = backdated
    await session.commit()

    await session.execute(
        update(Job)
        .where(Job.id == via_bulk.id)  # pyright: ignore[reportArgumentType]
        .values(status=JobStatus.CLOSED, closed_at=backdated)
    )
    await session.commit()

    await session.refresh(via_orm)
    await session.refresh(via_bulk)
    assert via_orm.closed_at == backdated
    assert via_bulk.closed_at == backdated


@pytest.mark.asyncio
async def test_closed_at_stamped_by_bulk_update_bypassing_the_orm(
    session: AsyncSession,
    company_with_user: CompanyProfile,
    make_job,
):
    """The database trigger, not the ORM hook, is the actual guarantee.

    A Core-level UPDATE never loads an instance, so the mapper-level hooks
    never fire. This is the shape a mass-close would be written in —
    the codebase already uses ``update(Application)`` this way — and getting a
    NULL anchor here would mean those candidates were never purged.
    """
    job = make_job(company_with_user.id, JobStatus.PUBLISHED)
    session.add(job)
    await session.commit()
    assert job.closed_at is None

    await session.execute(
        update(Job).where(Job.id == job.id).values(status=JobStatus.CLOSED)  # pyright: ignore[reportArgumentType]
    )
    await session.commit()

    await session.refresh(job)
    assert job.status == JobStatus.CLOSED
    assert job.closed_at is not None


@pytest.mark.asyncio
async def test_bulk_reopen_clears_closed_at(
    session: AsyncSession,
    company_with_user: CompanyProfile,
    make_job,
):
    """The trigger clears on the way out too, not just on the way in."""
    job = make_job(company_with_user.id, JobStatus.CLOSED)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.closed_at is not None

    await session.execute(
        update(Job).where(Job.id == job.id).values(status=JobStatus.PUBLISHED)  # pyright: ignore[reportArgumentType]
    )
    await session.commit()

    await session.refresh(job)
    assert job.closed_at is None


@pytest.mark.asyncio
async def test_bulk_edit_of_closed_job_does_not_move_closed_at(
    session: AsyncSession,
    company_with_user: CompanyProfile,
    make_job,
):
    """`UPDATE OF status` means a title-only write never fires the trigger."""
    job = make_job(company_with_user.id, JobStatus.CLOSED)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    anchor = job.closed_at

    await session.execute(
        update(Job).where(Job.id == job.id).values(title="Bulk Renamed")  # pyright: ignore[reportArgumentType]
    )
    await session.commit()

    await session.refresh(job)
    assert job.closed_at == anchor


@pytest.mark.asyncio
async def test_reclosing_does_not_move_closed_at(
    session: AsyncSession,
    company_with_user: CompanyProfile,
    make_job,
):
    """Re-setting CLOSED on an already-closed job must not restart retention.

    This is the shape of an admin re-saving the edit form: the PATCH carries
    ``status: CLOSED`` unchanged. It holds at two levels — SQLAlchemy reports no
    attribute history when a value is re-set to itself, so the ORM hook skips;
    and the trigger's ``OLD.status IS DISTINCT FROM 'CLOSED'`` guard makes the
    write a no-op even when the ORM is bypassed. Pinned because a regression
    here silently re-retains every candidate who applied to the job.
    """
    job = make_job(company_with_user.id, JobStatus.CLOSED)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    anchor = job.closed_at

    job.status = JobStatus.CLOSED  # re-set to the same value, via the ORM
    job.title = "Re-saved"
    await session.commit()
    await session.refresh(job)
    assert job.closed_at == anchor

    await session.execute(  # and again, bypassing the ORM
        update(Job).where(Job.id == job.id).values(status=JobStatus.CLOSED)  # pyright: ignore[reportArgumentType]
    )
    await session.commit()
    await session.refresh(job)
    assert job.closed_at == anchor


@pytest.mark.asyncio
async def test_explicit_closed_at_survives_when_status_unchanged(
    session: AsyncSession,
    company_with_user: CompanyProfile,
    make_job,
):
    """Backdating the anchor is how the purge fixtures build aged jobs."""
    job = make_job(company_with_user.id, JobStatus.CLOSED)
    session.add(job)
    await session.commit()

    backdated = datetime.now(timezone.utc) - timedelta(days=400)
    job.closed_at = backdated
    await session.commit()

    await session.refresh(job)
    assert job.closed_at is not None
    assert (job.closed_at - backdated).total_seconds() < 1
