"""Failed-login throttling per (email, client IP).

Policy (NIST SP 800-63B-4 rate limiting; OWASP temporary, escalating lockout):

* Each (email, client IP) pair gets ``FREE_FAILURES`` free failures. From then
  on that pair alone is blocked for 1, 2, 4, 8, then 15 minutes (capped), and
  the block applies even to the correct password from that source.
* The same account from any other address is never blocked by it, so knowing
  someone's email is no longer enough to lock them out (the old per-account
  lock was). Counters reset on a successful login from the pair, on password
  reset (all of the email's pairs), and after ``DECAY`` without failures.
* Unknown emails are throttled exactly like real ones, so a 429 never reveals
  whether an account exists.
* Distributed attacks on one account (many IPs) trip an alert-only backstop:
  ``login_account_under_attack`` is logged, nothing is blocked.

Writes use their own session: a failed login raises, which rolls back the
request's session, and the failure must still be recorded. Event names
(``login_failed``, ``login_account_locked``, ``login_lockout_hit``) are the
ones the observability alerts and docs already use.
"""

import hashlib
import hmac
import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rs_shared.core.infrastructure.config import get_jwt_secret_key
from rs_shared.services.exceptions import AccountLockedError
from rs_shared.services.utils.audit import record_audit_event

logger = logging.getLogger(__name__)

FREE_FAILURES = 5
_FIRST_BLOCK = timedelta(minutes=1)
MAX_BLOCK = timedelta(minutes=15)
DECAY = timedelta(hours=24)
BACKSTOP_WINDOW = timedelta(hours=1)
BACKSTOP_FAILURES = 100

_UNKNOWN_IP = "unknown"


def _session_factory() -> async_sessionmaker[AsyncSession]:
    """Indirection so tests can point the throttle at the per-run test DB."""
    from rs_shared.core.infrastructure.database import async_session

    return async_session


def email_prefix(email: str) -> str:
    """First two chars of the local part — loggable without storing PII."""
    local = email.split("@")[0]
    return f"{local[:2]}***"


def _email_hash(email: str) -> str:
    """Keyed hash of the normalized email, so typed emails aren't stored."""
    key = get_jwt_secret_key().encode("utf-8")
    normalized = email.lower().strip().encode("utf-8")
    return hmac.new(key, normalized, hashlib.sha256).hexdigest()


def _ip_key(client_ip: str | None) -> str:
    return client_ip or _UNKNOWN_IP


def block_duration(failures: int) -> timedelta | None:
    """Block length after ``failures`` consecutive failures, or None (free)."""
    if failures < FREE_FAILURES:
        return None
    doublings = failures - FREE_FAILURES
    # Cap the exponent before computing, so a long attack can't overflow.
    if doublings >= 4:
        return MAX_BLOCK
    return min(_FIRST_BLOCK * (2**doublings), MAX_BLOCK)


async def check_login_allowed(email: str, client_ip: str | None) -> None:
    """Raise AccountLockedError while this (email, IP) pair is blocked."""
    async with _session_factory()() as session:
        blocked_until = (
            await session.execute(
                text(
                    "SELECT blocked_until FROM login_throttle "
                    "WHERE email_hash = :h AND client_ip = :ip"
                ),
                {"h": _email_hash(email), "ip": _ip_key(client_ip)},
            )
        ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if blocked_until is None or blocked_until <= now:
        return
    ttl = (blocked_until - now).total_seconds()
    logger.warning(
        "login_lockout_hit",
        extra={"email_prefix": email_prefix(email), "ttl_s": int(ttl), "ip": client_ip},
    )
    raise AccountLockedError(minutes_remaining=math.ceil(ttl / 60))


async def record_login_failure(
    email: str, client_ip: str | None, *, user_id: int | None = None
) -> None:
    """Count a failure for the pair; start or extend its block at the threshold.

    One atomic upsert (no read-modify-write race); the counter restarts at 1
    when the pair's previous failure is older than ``DECAY``.

    ``user_id`` is set when the email belongs to an account (wrong password):
    a ``user.login_failed`` audit row is then written in this same transaction.
    The throttle table is wiped after ``DECAY``; the audit row is the lasting
    record. It rides on this commit rather than a second one so the wrong-
    password path costs one INSERT more than the unknown-email path, not a
    round of connection + commit (``authenticate_user`` equalises timing).
    Unknown emails get no row: no account to attach it to, and the attempted
    address must not be stored.
    """
    now = datetime.now(timezone.utc)
    h = _email_hash(email)
    async with _session_factory()() as session:
        failures: int = (
            await session.execute(
                text(
                    "INSERT INTO login_throttle "
                    "(email_hash, client_ip, failures, last_failure_at) "
                    "VALUES (:h, :ip, 1, :now) "
                    "ON CONFLICT (email_hash, client_ip) DO UPDATE SET "
                    "failures = CASE WHEN login_throttle.last_failure_at < :cutoff "
                    "THEN 1 ELSE login_throttle.failures + 1 END, "
                    "last_failure_at = :now "
                    "RETURNING failures"
                ),
                {"h": h, "ip": _ip_key(client_ip), "now": now, "cutoff": now - DECAY},
            )
        ).scalar_one()

        block = block_duration(failures)
        if block is not None:
            await session.execute(
                text(
                    "UPDATE login_throttle SET blocked_until = :until "
                    "WHERE email_hash = :h AND client_ip = :ip"
                ),
                {"until": now + block, "h": h, "ip": _ip_key(client_ip)},
            )

        recent_total: int = (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(failures), 0) FROM login_throttle "
                    "WHERE email_hash = :h AND last_failure_at >= :since"
                ),
                {"h": h, "since": now - BACKSTOP_WINDOW},
            )
        ).scalar_one()
        if user_id is not None:
            await record_audit_event(
                session,
                actor_user_id=None,
                action="user.login_failed",
                target_type="User",
                target_id=user_id,
                ip_address=client_ip,
            )
        await session.commit()

    prefix = email_prefix(email)
    if block is not None:
        logger.warning(
            "login_account_locked",
            extra={
                "email_prefix": prefix,
                "ip": client_ip,
                "attempt": failures,
                "block_s": int(block.total_seconds()),
            },
        )
    else:
        logger.warning(
            "login_failed",
            extra={"email_prefix": prefix, "attempt": failures, "ip": client_ip},
        )
    if recent_total >= BACKSTOP_FAILURES:
        # Alert-only by design: blocking the account for everyone here would
        # hand a distributed attacker the lockout this module exists to remove.
        logger.warning(
            "login_account_under_attack",
            extra={"email_prefix": prefix, "failures_last_hour": recent_total},
        )


async def clear_login_failures(email: str, client_ip: str | None) -> None:
    """Forget the pair's failures (successful login from it)."""
    async with _session_factory()() as session:
        await session.execute(
            text(
                "DELETE FROM login_throttle WHERE email_hash = :h AND client_ip = :ip"
            ),
            {"h": _email_hash(email), "ip": _ip_key(client_ip)},
        )
        await session.commit()


async def clear_all_login_failures(email: str) -> None:
    """Forget every pair for the email (password reset proves inbox ownership)."""
    async with _session_factory()() as session:
        await session.execute(
            text("DELETE FROM login_throttle WHERE email_hash = :h"),
            {"h": _email_hash(email)},
        )
        await session.commit()
