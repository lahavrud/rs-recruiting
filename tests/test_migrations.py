"""Execution tests for data migrations.

`alembic upgrade --sql` proves a migration's SQL renders; it does not prove the
statements select the rows they are meant to. A data migration that matches
nothing — a stale enum literal, a renamed column, a join that silently excludes
everything — produces exactly the same clean output as one that worked. These
tests seed the state a migration is written to repair and run its real
statements against it.

Schema-only migrations are not covered here: dev and test build the schema from
``create_all`` rather than by running the chain (.claude/rules/migrations.md),
so the DDL those migrations emit is verified by the model tests instead.
"""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.enums import ApplicationStatus, JobStatus
from rs_shared.models import (
    Application,
    AuditLog,
    CandidateProfile,
    CompanyProfile,
    Job,
)

_VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _load_migration(stem: str) -> ModuleType:
    """Import a migration by file stem.

    Alembic's versions directory is not a package, so it cannot be imported
    normally — but loading by path lets a test run the migration's own SQL
    constants rather than a copy that can drift from them.
    """
    path = next(_VERSIONS.glob(f"{stem}_*.py"))
    spec = importlib.util.spec_from_file_location(stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _job(session: AsyncSession, company_id: int, status: JobStatus) -> Job:
    job = Job(
        company_id=company_id,
        title=f"{status.value} role",
        short_description="Short blurb for testing.",
        description="x",
        requirements=[{"text": "x"}, {"text": "y"}, {"text": "z"}],
        location="x",
        salary_min=15000,
        salary_max=25000,
        status=status,
    )
    session.add(job)
    await session.flush()
    return job


async def _application(
    session: AsyncSession, job: Job, email: str, status: ApplicationStatus
) -> Application:
    candidate = CandidateProfile(full_name="מועמד", email=email, phone="050-0000000")
    session.add(candidate)
    await session.flush()
    app = Application(job_id=job.id, candidate_id=candidate.id, status=status)
    session.add(app)
    await session.flush()
    return app


@pytest.mark.asyncio
async def test_sweep_stranded_active_applications(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """b8d1f04e37a2 repairs exactly the stranded rows and nothing else."""
    migration = _load_migration("b8d1f04e37a2")

    closed = await _job(session, company_with_user.id, JobStatus.CLOSED)
    published = await _job(session, company_with_user.id, JobStatus.PUBLISHED)

    stranded = await _application(
        session, closed, "stranded@test.com", ApplicationStatus.PENDING_ADMIN_REVIEW
    )
    stranded_late = await _application(
        session, closed, "offer@test.com", ApplicationStatus.OFFER
    )
    # Must be left alone: a terminal outcome on the same closed job, and an
    # in-flight application on a job that is still open.
    hired = await _application(
        session, closed, "hired@test.com", ApplicationStatus.HIRED
    )
    already_swept = await _application(
        session, closed, "swept@test.com", ApplicationStatus.JOB_CLOSED
    )
    live = await _application(
        session, published, "live@test.com", ApplicationStatus.INTERVIEWING
    )
    await session.commit()

    await session.execute(text(migration.AUDIT_SQL))
    await session.execute(text(migration.SWEEP_SQL))
    await session.commit()

    for app in (stranded, stranded_late, hired, already_swept, live):
        await session.refresh(app)

    assert stranded.status == ApplicationStatus.JOB_CLOSED
    assert stranded_late.status == ApplicationStatus.JOB_CLOSED
    assert hired.status == ApplicationStatus.HIRED
    assert already_swept.status == ApplicationStatus.JOB_CLOSED
    assert live.status == ApplicationStatus.INTERVIEWING


@pytest.mark.asyncio
async def test_sweep_writes_one_audit_row_per_repaired_application(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """The sweep is a silent bulk edit to candidate data — it must leave a trail."""
    migration = _load_migration("b8d1f04e37a2")

    closed = await _job(session, company_with_user.id, JobStatus.CLOSED)
    stranded = await _application(
        session, closed, "audit@test.com", ApplicationStatus.APPROVED_BY_ADMIN
    )
    await _application(session, closed, "hired2@test.com", ApplicationStatus.HIRED)
    await session.commit()

    await session.execute(text(migration.AUDIT_SQL))
    await session.execute(text(migration.SWEEP_SQL))
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

    assert len(rows) == 1  # only the stranded row, not the HIRED one
    assert rows[0].target_id == stranded.id
    assert rows[0].actor_user_id is None  # system-initiated, as the purge does
    assert "JOB_CLOSED (backfill:" in (rows[0].detail or "")
    assert str(closed.id) in (rows[0].detail or "")


@pytest.mark.asyncio
async def test_sweep_is_idempotent(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """A re-run must not re-sweep or duplicate audit rows.

    The migrate gate runs as a one-off ECS task; a retry after a transient
    failure re-runs the whole revision.
    """
    migration = _load_migration("b8d1f04e37a2")

    closed = await _job(session, company_with_user.id, JobStatus.CLOSED)
    await _application(
        session, closed, "idem@test.com", ApplicationStatus.PENDING_ADMIN_REVIEW
    )
    await session.commit()

    for _ in range(2):
        await session.execute(text(migration.AUDIT_SQL))
        await session.execute(text(migration.SWEEP_SQL))
        await session.commit()

    audit_rows = list(
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.target_type == "Application",  # pyright: ignore[reportArgumentType]
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1


@pytest.mark.asyncio
async def test_swept_rows_become_purgeable_again(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """The point of the sweep: restore these candidates to the retention policy.

    Left active, they would be preserved forever by the (correct) rule that an
    in-flight application holds its candidate back.
    """
    from unittest.mock import AsyncMock, patch

    from rs_shared.services.admin.candidates import (
        CANDIDATE_RETENTION_DAYS,
        purge_expired_candidates,
    )

    migration = _load_migration("b8d1f04e37a2")

    closed = await _job(session, company_with_user.id, JobStatus.CLOSED)
    await _application(
        session, closed, "expired@test.com", ApplicationStatus.PENDING_ADMIN_REVIEW
    )
    closed.closed_at = datetime.now(timezone.utc) - timedelta(
        days=CANDIDATE_RETENTION_DAYS + 30
    )
    session.add(closed)
    await session.commit()

    with patch(
        "rs_shared.services.admin._candidates_purge.get_storage_provider"
    ) as factory:
        factory.return_value.delete_file = AsyncMock()
        assert await purge_expired_candidates(session) == 0  # held back while active

        await session.execute(text(migration.AUDIT_SQL))
        await session.execute(text(migration.SWEEP_SQL))
        await session.commit()

        assert await purge_expired_candidates(session) == 1
