"""The code step of an MFA login (#1177): challenge in, user out.

* A correct password for an MFA user yields a challenge (single-use, 5
  minutes, at most ``MAX_CHALLENGE_ATTEMPTS`` codes) instead of tokens; only
  ``verify_challenge`` lets the caller issue them.
* Each attempt is reserved on the challenge *before* the code is checked, in
  its own committed session: concurrent guesses can't overrun the cap and the
  request's rollback can't hand an attempt back.
* A wrong code counts per account (``_mfa_lockout``) and per (email, IP)
  (``login_throttle``); a locked account or throttled pair is refused before
  any code is checked.
* The success path consumes the challenge with a conditional DELETE, so two
  concurrent correct answers can't both log in.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rs_shared.core.infrastructure.security import hash_token
from rs_shared.models import MfaChallenge, User
from rs_shared.services.auth import login_throttle
from rs_shared.services.auth._mfa_codes import (
    check_totp,
    consume_recovery_code,
    remaining_recovery_codes,
)
from rs_shared.services.auth._mfa_lockout import (
    clear_failures,
    ensure_not_locked,
    record_failed_code,
)
from rs_shared.services.auth._mfa_notify import MfaEvent, notify_mfa_event
from rs_shared.services.auth.mfa import get_user_mfa
from rs_shared.services.exceptions import (
    InvalidMfaCodeError,
    MfaChallengeExpiredError,
)
from rs_shared.services.utils.audit import record_audit_event

logger = logging.getLogger(__name__)

CHALLENGE_TTL = timedelta(minutes=5)
MAX_CHALLENGE_ATTEMPTS = 5


def _session_factory() -> async_sessionmaker[AsyncSession]:
    """Indirection so tests can point the attempt reservation at the test DB."""
    from rs_shared.core.infrastructure.database import async_session

    return async_session


async def create_challenge(
    session: AsyncSession, user: User, *, remember_me: bool
) -> str:
    """Start the code step of a login. Returns the raw challenge token.

    Replaces any earlier challenge of the user's: one live challenge per
    account, so a password holder can't stockpile them for more guesses.
    """
    assert user.id is not None
    await session.execute(
        delete(MfaChallenge).where(
            MfaChallenge.user_id == user.id  # pyright: ignore[reportArgumentType]
        )
    )
    raw = secrets.token_urlsafe(32)
    session.add(
        MfaChallenge(
            token_hash=hash_token(raw),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + CHALLENGE_TTL,
            remember_me=remember_me,
        )
    )
    await session.flush()
    return raw


async def _reserve_attempt(raw_challenge: str) -> tuple[int, int, bool] | None:
    """Take one attempt on a live challenge: (id, user_id, remember_me) or None.

    A single conditional UPDATE, committed on its own before any code is
    checked: concurrent guesses can't overrun the cap, and the request's
    rollback on a wrong code can't hand the attempt back.
    """
    async with _session_factory()() as attempt_session:
        row = (
            await attempt_session.execute(
                update(MfaChallenge)
                .where(
                    MfaChallenge.token_hash == hash_token(raw_challenge),  # pyright: ignore[reportArgumentType]
                    MfaChallenge.expires_at > datetime.now(timezone.utc),  # pyright: ignore[reportArgumentType]
                    MfaChallenge.attempts < MAX_CHALLENGE_ATTEMPTS,  # pyright: ignore[reportArgumentType]
                )
                .values(attempts=MfaChallenge.attempts + 1)
                .returning(
                    MfaChallenge.id,  # pyright: ignore[reportArgumentType]
                    MfaChallenge.user_id,  # pyright: ignore[reportArgumentType]
                    MfaChallenge.remember_me,  # pyright: ignore[reportArgumentType]
                )
            )
        ).first()
        await attempt_session.commit()
    return (row[0], row[1], row[2]) if row else None


async def verify_challenge(
    session: AsyncSession,
    raw_challenge: str,
    *,
    code: str | None = None,
    recovery_code: str | None = None,
    client_ip: str | None = None,
) -> tuple[User, bool]:
    """Complete a login's code step. Returns (user, remember_me).

    Exactly one of ``code`` / ``recovery_code`` is expected. Raises
    ``MfaChallengeExpiredError`` for an unknown, expired, used-up or already
    consumed challenge (the client goes back to the password step),
    ``MfaLockedError`` / ``AccountLockedError`` while the account or the
    (email, IP) pair is locked (also for the wrong code that locks it), and
    ``InvalidMfaCodeError`` for a wrong or replayed code. Must run inside
    ``transactional()`` (it queues email).
    """
    reserved = await _reserve_attempt(raw_challenge)
    if reserved is None:
        raise MfaChallengeExpiredError("mfa_challenge_expired")
    challenge_id, user_id, remember_me = reserved

    user = await session.get(User, user_id)
    mfa = await get_user_mfa(session, user_id)
    if user is None or not user.is_active or mfa is None or mfa.enabled_at is None:
        raise MfaChallengeExpiredError("mfa_challenge_expired")

    now = datetime.now(timezone.utc)
    ensure_not_locked(mfa, now)
    # A throttled (email, IP) pair is refused before any code is checked.
    await login_throttle.check_login_allowed(user.email, client_ip)

    # The request schema guarantees exactly one of code / recovery_code.
    used_recovery = not code
    if code:
        ok = await check_totp(session, mfa, code, now)
    else:
        ok = await consume_recovery_code(session, user_id, recovery_code or "")

    if not ok:
        locked = await record_failed_code(user_id, user.email, client_ip)
        raise locked or InvalidMfaCodeError("invalid_mfa_code")

    # Consume this challenge (and any other pending one of the user's). If a
    # concurrent request already consumed it, this one loses and rolls back
    # with everything it claimed (time-step, recovery code).
    consumed = await session.execute(
        delete(MfaChallenge)
        .where(MfaChallenge.user_id == user_id)  # pyright: ignore[reportArgumentType]
        .returning(MfaChallenge.id)  # pyright: ignore[reportArgumentType]
    )
    if challenge_id not in {row[0] for row in consumed.all()}:
        raise MfaChallengeExpiredError("mfa_challenge_expired")

    clear_failures(mfa)
    if used_recovery:
        remaining = await remaining_recovery_codes(session, user_id)
        await record_audit_event(
            session,
            actor_user_id=user_id,
            action="mfa_recovery_code_used",
            target_type="User",
            target_id=user_id,
            detail=f"remaining={remaining}",
            ip_address=client_ip,
        )
        await notify_mfa_event(
            session,
            user.email,
            MfaEvent.RECOVERY_CODE_USED,
            ip=client_ip,
            remaining=remaining,
        )
        logger.warning(
            "mfa_recovery_code_used",
            extra={"user_id": user_id, "remaining": remaining},
        )
    await login_throttle.clear_login_failures(user.email, client_ip)
    return user, remember_me
