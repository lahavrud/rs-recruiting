"""Tests for per-(email, client IP) login throttling."""

import logging
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from rs_shared.models import LoginThrottle
from rs_shared.services.admin.maintenance import LOGIN_THROTTLE_RETENTION
from rs_shared.services.auth import login_throttle
from rs_shared.services.auth.login_throttle import (
    BACKSTOP_FAILURES,
    DECAY,
    FREE_FAILURES,
    MAX_BLOCK,
    block_duration,
    check_login_allowed,
    clear_all_login_failures,
    clear_login_failures,
    record_login_failure,
)
from rs_shared.services.exceptions import AccountLockedError
from tests.conftest import TestSessionLocal, audit_rows

# asyncio_mode = "auto" picks up the async tests; a module-wide asyncio mark
# would also land on the sync ones, which pytest warns about.
pytestmark = pytest.mark.real_login_throttle

EMAIL = "victim@example.com"
ATTACKER = "203.0.113.10"
OWNER = "198.51.100.20"


async def _fail(n: int, email: str = EMAIL, ip: str | None = ATTACKER) -> None:
    for _ in range(n):
        await record_login_failure(email, ip)


async def _row(email: str = EMAIL, ip: str = ATTACKER) -> LoginThrottle | None:
    async with TestSessionLocal() as session:
        return (
            await session.execute(
                select(LoginThrottle).where(
                    LoginThrottle.email_hash == login_throttle._email_hash(email),  # pyright: ignore[reportArgumentType]
                    LoginThrottle.client_ip == ip,  # pyright: ignore[reportArgumentType]
                )
            )
        ).scalar_one_or_none()


async def _age_row(by: timedelta, email: str = EMAIL, ip: str = ATTACKER) -> None:
    async with TestSessionLocal() as session:
        await session.execute(
            update(LoginThrottle)
            .where(
                LoginThrottle.email_hash == login_throttle._email_hash(email),  # pyright: ignore[reportArgumentType]
                LoginThrottle.client_ip == ip,  # pyright: ignore[reportArgumentType]
            )
            .values(
                last_failure_at=LoginThrottle.last_failure_at - by,
                blocked_until=None,
            )
        )
        await session.commit()


def test_block_schedule_doubles_and_caps():
    assert [block_duration(n) for n in range(FREE_FAILURES)] == [None] * FREE_FAILURES
    minutes = [
        block_duration(n).total_seconds() / 60  # type: ignore[union-attr]
        for n in range(FREE_FAILURES, FREE_FAILURES + 7)
    ]
    assert minutes == [1, 2, 4, 8, 15, 15, 15]
    assert block_duration(10_000) == MAX_BLOCK


async def test_free_failures_then_the_pair_is_blocked(test_db):
    await _fail(FREE_FAILURES - 1)
    await check_login_allowed(EMAIL, ATTACKER)  # still allowed

    await _fail(1)
    with pytest.raises(AccountLockedError) as exc:
        await check_login_allowed(EMAIL, ATTACKER)
    assert exc.value.minutes_remaining == 1


async def test_block_never_spills_onto_another_address(test_db):
    """The point of the change: knowing an email is no longer enough to lock
    its owner out."""
    await _fail(FREE_FAILURES + 3)
    with pytest.raises(AccountLockedError):
        await check_login_allowed(EMAIL, ATTACKER)
    await check_login_allowed(EMAIL, OWNER)  # owner unaffected


async def test_email_is_normalized_and_never_stored(test_db):
    await _fail(1, email="  Victim@Example.COM ")
    row = await _row()
    assert row is not None and row.failures == 1
    assert EMAIL not in row.email_hash and len(row.email_hash) == 64


async def test_missing_ip_is_its_own_bucket(test_db):
    await _fail(FREE_FAILURES, ip=None)
    with pytest.raises(AccountLockedError):
        await check_login_allowed(EMAIL, None)
    await check_login_allowed(EMAIL, ATTACKER)


async def test_counter_restarts_after_decay(test_db):
    await _fail(FREE_FAILURES + 2)
    await _age_row(DECAY + timedelta(minutes=1))

    await _fail(1)
    row = await _row()
    assert row is not None and row.failures == 1
    await check_login_allowed(EMAIL, ATTACKER)


async def test_success_clears_only_that_pair(test_db):
    await _fail(3, ip=ATTACKER)
    await _fail(3, ip=OWNER)
    await clear_login_failures(EMAIL, OWNER)
    assert await _row(ip=OWNER) is None
    assert (await _row(ip=ATTACKER)) is not None


async def test_password_reset_clears_every_pair(test_db):
    await _fail(FREE_FAILURES, ip=ATTACKER)
    await _fail(FREE_FAILURES, ip=OWNER)
    await clear_all_login_failures(EMAIL)
    await check_login_allowed(EMAIL, ATTACKER)
    await check_login_allowed(EMAIL, OWNER)


async def test_backstop_alerts_but_blocks_nobody(test_db, caplog):
    """Many IPs against one account log an alert; a fresh address still gets in."""
    per_ip = FREE_FAILURES - 1  # each source stays under its own block
    ips = [f"203.0.113.{i}" for i in range(BACKSTOP_FAILURES // per_ip + 1)]
    with caplog.at_level(logging.WARNING, logger=login_throttle.__name__):
        for ip in ips:
            await _fail(per_ip, ip=ip)

    assert any(r.getMessage() == "login_account_under_attack" for r in caplog.records)
    await check_login_allowed(EMAIL, OWNER)


def test_retention_matches_decay():
    """maintenance.py can't import the auth package; keep the two in step."""
    assert LOGIN_THROTTLE_RETENTION == DECAY


async def test_block_expiry_is_reported_in_minutes(test_db):
    await _fail(FREE_FAILURES + 3)  # 8-minute block
    with pytest.raises(AccountLockedError) as exc:
        await check_login_allowed(EMAIL, ATTACKER)
    assert exc.value.minutes_remaining == 8
    row = await _row()
    assert row is not None and row.blocked_until is not None
    assert row.blocked_until > datetime.now(timezone.utc) + timedelta(minutes=7)


async def test_failure_on_a_real_account_writes_a_lasting_audit_row(test_db):
    """The throttle row decays after 24h; the audit row is the lasting record."""
    await record_login_failure(EMAIL, ATTACKER, user_id=42)

    [row] = await audit_rows("user.login_failed")
    assert (row.target_type, row.target_id) == ("User", 42)
    assert (row.actor_user_id, row.ip_address, row.detail) == (None, ATTACKER, None)


async def test_failure_on_an_unknown_email_writes_no_audit_row(test_db):
    await record_login_failure("nobody@example.com", ATTACKER)

    assert await audit_rows("user.login_failed") == []
