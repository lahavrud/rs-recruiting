"""Tests for the audit service helpers."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import AuditLog, LoginThrottle
from rs_shared.services.utils.audit import (
    list_audit_events,
    record_audit_event,
    record_audit_event_best_effort,
)
from tests.conftest import audit_rows


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


def test_changed_fields_lists_only_differing_names_sorted():
    from types import SimpleNamespace

    from rs_shared.services.utils.audit import changed_fields

    target = SimpleNamespace(title="Old", location="Haifa", tags=["a"])
    updates = {"title": "New", "location": "Haifa", "tags": ["a", "b"]}

    assert changed_fields(target, updates) == ["tags", "title"]


def test_changed_fields_empty_when_nothing_differs():
    from types import SimpleNamespace

    from rs_shared.services.utils.audit import changed_fields

    assert changed_fields(SimpleNamespace(title="Same"), {"title": "Same"}) == []


@pytest.mark.asyncio
async def test_record_audit_event_truncates_an_overlong_ip(session: AsyncSession):
    """A malformed forwarded value must not fail the write it rides on."""
    await record_audit_event(
        session,
        actor_user_id=None,
        action="t.ip",
        target_type="User",
        target_id=1,
        ip_address="2001:db8::1, " * 10,
    )
    await session.commit()

    [row] = await audit_rows("t.ip")
    assert row.ip_address is not None and len(row.ip_address) == 45


@pytest.mark.asyncio
async def test_best_effort_audit_failure_keeps_the_callers_change(
    session: AsyncSession,
):
    """The savepoint drops only the audit row; the caller's write still commits."""
    session.add(
        LoginThrottle(
            email_hash="h",
            client_ip="ip",
            failures=1,
            last_failure_at=datetime.now(timezone.utc),
        )
    )
    with patch(
        "rs_shared.services.utils.audit.record_audit_event",
        new=AsyncMock(side_effect=RuntimeError("audit down")),
    ):
        await record_audit_event_best_effort(
            session,
            actor_user_id=None,
            action="t.best_effort",
            target_type="User",
            target_id=1,
        )
    await session.commit()

    kept = await session.execute(
        select(LoginThrottle).where(LoginThrottle.email_hash == "h")  # pyright: ignore[reportArgumentType]
    )
    assert kept.scalar_one_or_none() is not None
    assert await audit_rows("t.best_effort") == []


@pytest.mark.asyncio
async def test_best_effort_audit_writes_the_row_when_healthy(session: AsyncSession):
    await record_audit_event_best_effort(
        session, actor_user_id=None, action="t.ok", target_type="User", target_id=2
    )
    await session.commit()

    [row] = await audit_rows("t.ok")
    assert row.target_id == 2
