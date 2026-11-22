"""Tests for the per-account lock on wrong login codes."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import AuditLog, EmailOutbox, MfaChallenge, User, UserMfa
from rs_shared.services.auth._mfa_lockout import (
    LOCK_FREE_FAILURES,
    MAX_LOCK,
    clear_failures,
    ensure_not_locked,
    lock_duration,
    record_failed_code,
    reset_mfa_lock,
)
from rs_shared.services.exceptions import MfaLockedError

IP = "203.0.113.9"


def test_lock_schedule_doubles_from_five_minutes_and_caps_at_an_hour():
    assert [lock_duration(n) for n in range(LOCK_FREE_FAILURES)] == [None] * 5
    minutes = [
        lock_duration(n).total_seconds() / 60  # type: ignore[union-attr]
        for n in range(LOCK_FREE_FAILURES, LOCK_FREE_FAILURES + 6)
    ]
    assert minutes == [5, 10, 20, 40, 60, 60]
    assert lock_duration(10_000) == MAX_LOCK


def test_ensure_not_locked():
    now = datetime.now(timezone.utc)
    mfa = UserMfa(user_id=1, secret_encrypted="ct")
    ensure_not_locked(mfa, now)  # never locked
    mfa.locked_until = now - timedelta(seconds=1)
    ensure_not_locked(mfa, now)  # lock over
    mfa.locked_until = now + timedelta(seconds=61)
    with pytest.raises(MfaLockedError) as exc:
        ensure_not_locked(mfa, now)
    assert exc.value.minutes_remaining == 2


def test_clear_failures():
    mfa = UserMfa(
        user_id=1,
        secret_encrypted="ct",
        failed_attempts=7,
        locked_until=datetime.now(timezone.utc),
    )
    clear_failures(mfa)
    assert mfa.failed_attempts == 0 and mfa.locked_until is None


async def _mfa_row(session: AsyncSession, user: User, failures: int) -> None:
    session.add(
        UserMfa(user_id=user.id, secret_encrypted="ct", failed_attempts=failures)
    )
    await session.commit()


async def test_failures_below_the_threshold_do_not_lock(
    session: AsyncSession, admin_user: User
):
    await _mfa_row(session, admin_user, 0)
    assert admin_user.id is not None
    assert await record_failed_code(admin_user.id, admin_user.email, IP) is None

    row = await session.get(UserMfa, admin_user.id)
    assert row is not None and row.failed_attempts == 1 and row.locked_until is None
    audit = (await session.execute(select(AuditLog))).scalar_one()
    assert audit.action == "mfa_verify_failed"
    assert audit.detail == "consecutive=1 context=login"
    assert (await session.execute(select(EmailOutbox))).first() is None


async def test_the_first_lock_emails_the_owner_once(
    session: AsyncSession, admin_user: User
):
    await _mfa_row(session, admin_user, LOCK_FREE_FAILURES - 1)
    assert admin_user.id is not None
    first = await record_failed_code(admin_user.id, admin_user.email, IP)
    second = await record_failed_code(admin_user.id, admin_user.email, IP)

    # The failure that locks reports it, with the lock's length.
    assert first is not None and first.minutes_remaining == 5
    assert second is not None and second.minutes_remaining == 10
    session.expire_all()
    row = await session.get(UserMfa, admin_user.id)
    assert row is not None and row.locked_until is not None
    assert row.locked_until > datetime.now(timezone.utc) + timedelta(minutes=9)
    emails = (await session.execute(select(EmailOutbox))).scalars().all()
    assert len(emails) == 1 and emails[0].to_addrs == [admin_user.email]
    assert "ניסיונות כניסה חשודים" in emails[0].subject


async def test_record_survives_without_an_mfa_row(
    session: AsyncSession, admin_user: User
):
    assert admin_user.id is not None
    await record_failed_code(admin_user.id, admin_user.email, None)
    detail = (await session.execute(select(AuditLog.detail))).scalar_one()  # pyright: ignore[reportArgumentType]
    assert detail == "consecutive=0 context=login"


async def test_context_is_recorded(session: AsyncSession, admin_user: User):
    await _mfa_row(session, admin_user, 0)
    assert admin_user.id is not None
    await record_failed_code(admin_user.id, admin_user.email, IP, context="regenerate")
    detail = (await session.execute(select(AuditLog.detail))).scalar_one()  # pyright: ignore[reportArgumentType]
    assert detail == "consecutive=1 context=regenerate"


async def test_reset_mfa_lock_clears_lock_and_pending_challenges(
    session: AsyncSession, admin_user: User
):
    await _mfa_row(session, admin_user, LOCK_FREE_FAILURES + 2)
    assert admin_user.id is not None
    session.add(
        MfaChallenge(
            token_hash="h",
            user_id=admin_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            remember_me=False,
        )
    )
    await session.execute(
        update(UserMfa).values(
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=20)
        )
    )
    await session.commit()

    await reset_mfa_lock(session, admin_user.id)
    await session.commit()

    session.expire_all()
    row = await session.get(UserMfa, admin_user.id)
    assert row is not None and row.failed_attempts == 0 and row.locked_until is None
    assert (await session.execute(select(MfaChallenge))).first() is None


async def test_a_failed_audit_write_keeps_the_lock_count(
    session: AsyncSession, admin_user: User
):
    await _mfa_row(session, admin_user, LOCK_FREE_FAILURES - 1)
    assert admin_user.id is not None
    with patch(
        "rs_shared.services.utils.audit.record_audit_event",
        new=AsyncMock(side_effect=RuntimeError("audit down")),
    ):
        locked = await record_failed_code(admin_user.id, admin_user.email, IP)

    assert locked is not None
    session.expire_all()
    row = await session.get(UserMfa, admin_user.id)
    assert row is not None and row.failed_attempts == LOCK_FREE_FAILURES
    assert row.locked_until is not None
