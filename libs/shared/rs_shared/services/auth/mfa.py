"""TOTP second factor: enrolment, login challenges, recovery codes (#1177).

Policy:

* **Enrolment** issues a secret (stored encrypted, ``enabled_at`` NULL) and is
  confirmed by a valid code. Confirming turns MFA on, issues recovery codes and
  revokes every *other* session, so no password-only session outlives it.
* **Login**: a correct password for an MFA user yields a challenge (single-use,
  5 minutes, dead after ``MAX_CHALLENGE_FAILURES`` bad codes) instead of tokens.
  ``verify_challenge`` takes a TOTP or an unused recovery code and only then may
  the caller issue tokens.
* **Replay**: each user's highest accepted time-step is stored; a code for that
  step or an earlier one is refused, claimed atomically so two concurrent
  submissions of one code cannot both pass. ±1 step of clock skew is allowed.
* **Abuse**: a bad code counts as a login failure for the (email, IP) pair
  (``login_throttle``), and a throttled pair is refused before any code check.
* Admins can't switch MFA off; ``scripts/reset_mfa.py`` is the break-glass.

Failed verifications are written through a separate session: the request
raises afterwards, which rolls its own session back (same reason as
``login_throttle``).
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rs_shared.core.infrastructure.security import encrypt_mfa_secret, hash_token
from rs_shared.models import MfaChallenge, RefreshToken, User, UserMfa
from rs_shared.services.auth import login_throttle
from rs_shared.services.auth._mfa_codes import (
    check_totp,
    consume_recovery_code,
    remaining_recovery_codes,
    replace_recovery_codes,
)
from rs_shared.services.exceptions import (
    InvalidMfaCodeError,
    MfaAlreadyEnabledError,
    MfaChallengeExpiredError,
    MfaNotEnrolledError,
)
from rs_shared.services.utils.audit import record_audit_event

logger = logging.getLogger(__name__)

ISSUER = "RS Recruiting"
CHALLENGE_TTL = timedelta(minutes=5)
MAX_CHALLENGE_FAILURES = 5


def _session_factory() -> async_sessionmaker[AsyncSession]:
    """Indirection so tests can point the failure writes at the test DB."""
    from rs_shared.core.infrastructure.database import async_session

    return async_session


# ── helpers ──────────────────────────────────────────────────────────────────


async def get_user_mfa(session: AsyncSession, user_id: int) -> UserMfa | None:
    result = await session.execute(
        select(UserMfa).where(UserMfa.user_id == user_id)  # pyright: ignore[reportArgumentType]
    )
    return result.scalar_one_or_none()


async def is_mfa_enabled(session: AsyncSession, user_id: int) -> bool:
    """True once enrolment is confirmed (a pending secret doesn't count)."""
    mfa = await get_user_mfa(session, user_id)
    return mfa is not None and mfa.enabled_at is not None


# ── enrolment ────────────────────────────────────────────────────────────────


async def start_enrolment(session: AsyncSession, user: User) -> tuple[str, str]:
    """Issue a (pending) TOTP secret. Returns (secret, otpauth URI).

    Calling it again before confirming replaces the pending secret, so a
    half-finished enrolment can simply be restarted.
    """
    assert user.id is not None
    mfa = await get_user_mfa(session, user.id)
    if mfa is not None and mfa.enabled_at is not None:
        raise MfaAlreadyEnabledError("mfa_already_enabled")

    secret = pyotp.random_base32()
    encrypted = encrypt_mfa_secret(secret)
    if mfa is None:
        session.add(UserMfa(user_id=user.id, secret_encrypted=encrypted))
    else:
        mfa.secret_encrypted = encrypted
        mfa.last_used_step = 0
        mfa.created_at = datetime.now(timezone.utc)
    await session.flush()

    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=ISSUER)
    return secret, uri


async def confirm_enrolment(
    session: AsyncSession,
    user: User,
    code: str,
    *,
    keep_session_id: int | None,
    client_ip: str | None = None,
) -> list[str]:
    """Turn MFA on after a valid code. Returns the recovery codes (shown once).

    Revokes every refresh token except ``keep_session_id`` (the session doing
    the enrolment), so sessions that only ever proved the password end here.
    """
    assert user.id is not None
    mfa = await get_user_mfa(session, user.id)
    if mfa is None:
        raise MfaNotEnrolledError("mfa_not_enrolled")
    if mfa.enabled_at is not None:
        raise MfaAlreadyEnabledError("mfa_already_enabled")
    if not await check_totp(session, mfa, code):
        raise InvalidMfaCodeError("invalid_mfa_code")

    mfa.enabled_at = datetime.now(timezone.utc)
    codes = await replace_recovery_codes(session, user.id)

    revoke = delete(RefreshToken).where(
        RefreshToken.user_id == user.id  # pyright: ignore[reportArgumentType]
    )
    if keep_session_id is not None:
        revoke = revoke.where(
            RefreshToken.id != keep_session_id  # pyright: ignore[reportArgumentType]
        )
    await session.execute(revoke)

    await record_audit_event(
        session,
        actor_user_id=user.id,
        action="mfa_enrolled",
        target_type="User",
        target_id=user.id,
        ip_address=client_ip,
    )
    logger.info("mfa_enrolled", extra={"user_id": user.id, "ip": client_ip})
    return codes


async def regenerate_recovery_codes(
    session: AsyncSession, user: User, code: str, *, client_ip: str | None = None
) -> list[str]:
    """Replace all recovery codes; requires a current TOTP code."""
    assert user.id is not None
    mfa = await get_user_mfa(session, user.id)
    if mfa is None or mfa.enabled_at is None:
        raise MfaNotEnrolledError("mfa_not_enrolled")
    if not await check_totp(session, mfa, code):
        raise InvalidMfaCodeError("invalid_mfa_code")
    codes = await replace_recovery_codes(session, user.id)
    await record_audit_event(
        session,
        actor_user_id=user.id,
        action="mfa_recovery_codes_regenerated",
        target_type="User",
        target_id=user.id,
        ip_address=client_ip,
    )
    return codes


# ── login challenge ──────────────────────────────────────────────────────────


async def create_challenge(
    session: AsyncSession, user: User, *, remember_me: bool
) -> str:
    """Start the code step of a login. Returns the raw challenge token."""
    assert user.id is not None
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


async def _record_failed_verify(
    challenge_id: int, user_id: int, email: str, client_ip: str | None
) -> None:
    """Count a bad code on the challenge, audit it (own session), throttle."""
    async with _session_factory()() as fail_session:
        await fail_session.execute(
            update(MfaChallenge)
            .where(MfaChallenge.id == challenge_id)  # pyright: ignore[reportArgumentType]
            .values(failed_attempts=MfaChallenge.failed_attempts + 1)
        )
        await record_audit_event(
            fail_session,
            actor_user_id=user_id,
            action="mfa_verify_failed",
            target_type="User",
            target_id=user_id,
            ip_address=client_ip,
        )
        await fail_session.commit()
    logger.warning("mfa_verify_failed", extra={"user_id": user_id, "ip": client_ip})
    await login_throttle.record_login_failure(email, client_ip)


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
    ``MfaChallengeExpiredError`` for an unknown, expired or exhausted
    challenge (the client goes back to the password step), and
    ``InvalidMfaCodeError`` for a wrong or replayed code.
    """
    result = await session.execute(
        select(MfaChallenge).where(
            MfaChallenge.token_hash == hash_token(raw_challenge)  # pyright: ignore[reportArgumentType]
        )
    )
    challenge = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if (
        challenge is None
        or challenge.expires_at < now
        or challenge.failed_attempts >= MAX_CHALLENGE_FAILURES
    ):
        raise MfaChallengeExpiredError("mfa_challenge_expired")

    user = await session.get(User, challenge.user_id)
    mfa = await get_user_mfa(session, challenge.user_id)
    if user is None or not user.is_active or mfa is None or mfa.enabled_at is None:
        raise MfaChallengeExpiredError("mfa_challenge_expired")

    # A throttled (email, IP) pair is refused before any code is checked.
    await login_throttle.check_login_allowed(user.email, client_ip)

    used_recovery = False
    if code:
        ok = await check_totp(session, mfa, code, now)
    elif recovery_code:
        ok = used_recovery = await consume_recovery_code(
            session, challenge.user_id, recovery_code
        )
    else:
        ok = False

    if not ok:
        assert challenge.id is not None
        await _record_failed_verify(
            challenge.id, challenge.user_id, user.email, client_ip
        )
        raise InvalidMfaCodeError("invalid_mfa_code")

    remember_me = challenge.remember_me
    await session.delete(challenge)
    if used_recovery:
        remaining = await remaining_recovery_codes(session, challenge.user_id)
        await record_audit_event(
            session,
            actor_user_id=challenge.user_id,
            action="mfa_recovery_code_used",
            target_type="User",
            target_id=challenge.user_id,
            detail=f"remaining={remaining}",
            ip_address=client_ip,
        )
        logger.warning(
            "mfa_recovery_code_used",
            extra={"user_id": challenge.user_id, "remaining": remaining},
        )
    await login_throttle.clear_login_failures(user.email, client_ip)
    return user, remember_me
