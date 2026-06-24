"""Tests for the audit service helpers."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AuditLog
from src.services.utils.audit import list_audit_events, record_audit_event


@pytest.mark.asyncio
async def test_record_audit_event_persists_row(session: AsyncSession):
    await record_audit_event(
        session,
        actor_user_id=42,
        action="company.approve",
        target_type="CompanyProfile",
        target_id=7,
        detail="hello",
        ip_address="203.0.113.7",
    )
    await session.commit()

    rows = (await session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == 42
    assert row.action == "company.approve"
    assert row.target_type == "CompanyProfile"
    assert row.target_id == 7
    assert row.detail == "hello"
    assert row.ip_address == "203.0.113.7"
    assert row.created_at is not None


@pytest.mark.asyncio
async def test_record_audit_event_accepts_explicit_created_at(session: AsyncSession):
    """Callers (e.g. seed scripts) can backdate audit rows."""
    backdated = datetime(2025, 1, 1, tzinfo=timezone.utc)
    await record_audit_event(
        session,
        actor_user_id=42,
        action="application.status_change",
        target_type="Application",
        target_id=7,
        created_at=backdated,
    )
    await session.commit()

    row = (await session.execute(select(AuditLog))).scalar_one()
    assert row.created_at == backdated


@pytest.mark.asyncio
async def test_record_audit_event_allows_null_actor(session: AsyncSession):
    """System tasks (e.g. scheduled purge) write rows with actor_user_id=None."""
    await record_audit_event(
        session,
        actor_user_id=None,
        action="candidate.purge",
        target_type="CandidateProfile",
        target_id=1,
    )
    await session.commit()

    row = (await session.execute(select(AuditLog))).scalar_one()
    assert row.actor_user_id is None
    assert row.detail is None
    assert row.ip_address is None


@pytest.mark.asyncio
async def test_list_audit_events_filters_and_orders(session: AsyncSession):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        session.add(
            AuditLog(
                actor_user_id=1 if i % 2 == 0 else 2,
                action="company.approve",
                target_type="CompanyProfile" if i < 3 else "CandidateProfile",
                target_id=i,
                created_at=base + timedelta(minutes=i),
            )
        )
    await session.commit()

    page = await list_audit_events(session)
    assert [r.target_id for r in page.items] == [4, 3, 2, 1, 0]

    page = await list_audit_events(session, target_type="CandidateProfile")
    assert [r.target_id for r in page.items] == [4, 3]

    page = await list_audit_events(session, actor_user_id=1)
    assert [r.target_id for r in page.items] == [4, 2, 0]

    page = await list_audit_events(session, target_type="CompanyProfile", target_id=1)
    assert [r.target_id for r in page.items] == [1]


@pytest.mark.asyncio
async def test_list_audit_events_filters_by_date_range(session: AsyncSession):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        session.add(
            AuditLog(
                action="x",
                target_type="T",
                target_id=i,
                created_at=base + timedelta(days=i),
            )
        )
    await session.commit()

    page = await list_audit_events(
        session,
        from_dt=base + timedelta(days=1),
        to_dt=base + timedelta(days=3),
    )
    assert [r.target_id for r in page.items] == [3, 2, 1]
