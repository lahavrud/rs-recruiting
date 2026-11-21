"""Per-account lock on wrong login codes (#1177).

The login throttle counts failures per (email, IP), and a correct password
clears its pair. Alone, it lets anyone holding the password guess codes from
many addresses: 5 codes per challenge, a fresh challenge per login. So wrong
codes also count per *account*, from any address, and only a correct code (or
the break-glass reset) clears them: ``LOCK_FREE_FAILURES`` free, then the code
step is locked for 5, 10, 20, 40, then 60 minutes (capped). That bounds a
password holder to ~30 guesses a day (odds ~1e-4 against a 6-digit code).

Locking out the owner takes their password, and the first lock emails them
that it leaked. Writes go through their own session: the verify request rolls
back on the wrong code, and the count must survive it.
"""

import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.models import UserMfa
from rs_shared.services.auth import login_throttle
from rs_shared.services.auth._mfa_notify import MfaEvent, notify_mfa_event
from rs_shared.services.exceptions import MfaLockedError
from rs_shared.services.utils.audit import record_audit_event

logger = logging.getLogger(__name__)

LOCK_FREE_FAILURES = 5
_FIRST_LOCK = timedelta(minutes=5)
MAX_LOCK = timedelta(minutes=60)


def _session_factory() -> async_sessionmaker[AsyncSession]:
    """Indirection so tests can point the failure writes at the test DB."""
    from rs_shared.core.infrastructure.database import async_session

    return async_session


def lock_duration(failures: int) -> timedelta | None:
    """How long ``failures`` consecutive wrong codes lock the code step."""
    if failures < LOCK_FREE_FAILURES:
        return None
    doublings = min(failures - LOCK_FREE_FAILURES, 10)
    return min(_FIRST_LOCK * (2**doublings), MAX_LOCK)


def ensure_not_locked(mfa: UserMfa, now: datetime) -> None:
    """Raise ``MfaLockedError`` while the account's code step is locked."""
    if mfa.locked_until is not None and mfa.locked_until > now:
        minutes = math.ceil((mfa.locked_until - now).total_seconds() / 60)
        raise MfaLockedError(max(minutes, 1))


def clear_failures(mfa: UserMfa) -> None:
    """A correct code: the count starts over (caller's session)."""
    mfa.failed_attempts = 0
    mfa.locked_until = None


async def record_failed_code(user_id: int, email: str, client_ip: str | None) -> None:
    """Count a wrong login code: account lock, audit, owner email, IP throttle."""
    now = datetime.now(timezone.utc)
    async with _session_factory()() as fail_session:
        async with transactional(fail_session):
            row = (
                await fail_session.execute(
                    update(UserMfa)
                    .where(UserMfa.user_id == user_id)  # pyright: ignore[reportArgumentType]
                    .values(failed_attempts=UserMfa.failed_attempts + 1)
                    .returning(UserMfa.failed_attempts)  # pyright: ignore[reportArgumentType]
                )
            ).first()
            failures = row[0] if row else 0
            locked_for = lock_duration(failures)
            if locked_for is not None:
                await fail_session.execute(
                    update(UserMfa)
                    .where(UserMfa.user_id == user_id)  # pyright: ignore[reportArgumentType]
                    .values(locked_until=now + locked_for)
                )
            await record_audit_event(
                fail_session,
                actor_user_id=user_id,
                action="mfa_verify_failed",
                target_type="User",
                target_id=user_id,
                detail=f"consecutive={failures}",
                ip_address=client_ip,
            )
            # Only the first lock of a run emails: later ones would just spam.
            if failures == LOCK_FREE_FAILURES:
                logger.warning(
                    "mfa_account_locked", extra={"user_id": user_id, "ip": client_ip}
                )
                await notify_mfa_event(
                    fail_session, email, MfaEvent.LOCKED, ip=client_ip
                )
    logger.warning(
        "mfa_verify_failed",
        extra={"user_id": user_id, "ip": client_ip, "consecutive": failures},
    )
    await login_throttle.record_login_failure(email, client_ip)
