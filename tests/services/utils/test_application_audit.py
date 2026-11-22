"""Tests for the hard-deleted application audit helpers."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import Application, AuditLog
from rs_shared.services.utils.application_audit import (
    audit_application_deletes,
    deleted_application_ids,
)


async def _delete_rows(session: AsyncSession) -> list[AuditLog]:
    rows = await session.execute(
        select(AuditLog).where(AuditLog.action == "application.delete")  # pyright: ignore[reportArgumentType]
    )
    return list(rows.scalars().all())


@pytest.mark.asyncio
async def test_audit_application_deletes_writes_ids_only(
    session: AsyncSession, application: Application
):
    await audit_application_deletes(
        session,
        Application.id == application.id,  # pyright: ignore[reportArgumentType]
        actor_user_id=5,
        ip_address="203.0.113.20",
        cause="job_delete",
    )
    await session.commit()

    [row] = await _delete_rows(session)
    assert (row.target_type, row.target_id) == ("Application", application.id)
    assert (row.actor_user_id, row.ip_address) == (5, "203.0.113.20")
    assert row.detail == (
        f"job_id={application.job_id},candidate_id={application.candidate_id},"
        "status=PENDING_ADMIN_REVIEW,cause=job_delete"
    )


@pytest.mark.asyncio
async def test_audit_application_deletes_no_match_writes_nothing(
    session: AsyncSession,
):
    await audit_application_deletes(session, Application.id == -1)  # pyright: ignore[reportArgumentType]
    await session.commit()

    assert await _delete_rows(session) == []


@pytest.mark.asyncio
async def test_deleted_application_ids_matches_only_that_candidate(
    session: AsyncSession,
):
    """candidate 1 must not pick up candidate 12's rows (a prefix of the id)."""
    now = datetime.now(timezone.utc)
    for target_id, candidate_id in ((100, 1), (101, 12), (102, 1)):
        session.add(
            AuditLog(
                action="application.delete",
                target_type="Application",
                target_id=target_id,
                detail=f"job_id=9,candidate_id={candidate_id},status=OFFER",
                created_at=now,
            )
        )
    # A different action with a matching detail must not count either.
    session.add(
        AuditLog(
            action="application.status_change",
            target_type="Application",
            target_id=103,
            detail="job_id=9,candidate_id=1,status=OFFER",
            created_at=now,
        )
    )
    await session.commit()

    ids = (await session.execute(deleted_application_ids(1))).scalars().all()
    assert sorted(ids) == [100, 102]
