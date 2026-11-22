"""TOTP second factor: enrolment, recovery codes, status (#1177).

Policy:

* **Enrolment** issues a secret (stored encrypted, ``enabled_at`` NULL) and is
  confirmed by a valid code. Confirming turns MFA on, issues recovery codes,
  marks the enrolling session MFA-verified and revokes every *other* session.
* **Sessions**: a user with MFA on is refused any session whose refresh row
  isn't ``mfa_verified`` (``get_current_user``, ``refresh_user_tokens``). Only
  the code step and the enrolment set it.
* **Login**: a correct password for an MFA user yields a challenge instead of
  tokens; ``mfa_challenge`` runs that code step.
* **Replay**: each user's highest accepted time-step is stored; a code for that
  step or an earlier one is refused, claimed atomically so two concurrent
  submissions of one code cannot both pass. ±1 step of clock skew is allowed.
* **Owner emails** for enrolment, recovery-code use and regeneration, and the
  lock (``_mfa_notify``).
* Admins can't switch MFA off; ``scripts/reset_mfa.py`` is the break-glass.
"""

import logging
from datetime import datetime, timezone

import pyotp
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import encrypt_mfa_secret
from rs_shared.models import RefreshToken, User, UserMfa
from rs_shared.services.auth._mfa_codes import (
    check_totp,
    remaining_recovery_codes,
    replace_recovery_codes,
)
from rs_shared.services.auth._mfa_lockout import (
    clear_failures,
    ensure_not_locked,
    record_failed_code,
)
from rs_shared.services.auth._mfa_notify import MfaEvent, notify_mfa_event
from rs_shared.services.exceptions import (
    InvalidMfaCodeError,
    MfaAlreadyEnabledError,
    MfaNotEnrolledError,
)
from rs_shared.services.utils.audit import record_audit_event

logger = logging.getLogger(__name__)

ISSUER = "RS Recruiting"


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
    half-finished enrolment can simply be restarted. One upsert, so two
    concurrent starts (a double click) can't collide on the primary key;
    it never touches an enabled row.
    """
    assert user.id is not None
    mfa = await get_user_mfa(session, user.id)
    if mfa is not None and mfa.enabled_at is not None:
        raise MfaAlreadyEnabledError("mfa_already_enabled")

    secret = pyotp.random_base32()
    pending = {
        "secret_encrypted": encrypt_mfa_secret(secret),
        "last_used_step": 0,
        "created_at": datetime.now(timezone.utc),
    }
    stored = await session.execute(
        pg_insert(UserMfa)
        .values(user_id=user.id, **pending)
        .on_conflict_do_update(
            index_elements=[UserMfa.user_id],
            set_=pending,
            where=UserMfa.enabled_at.is_(None),  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
        )
        .returning(UserMfa.user_id)  # pyright: ignore[reportArgumentType]
    )
    if stored.first() is None:  # enabled by a concurrent confirm
        raise MfaAlreadyEnabledError("mfa_already_enabled")
    if mfa is not None:
        await session.refresh(mfa)  # the identity map still holds the old secret

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
        logger.warning(
            "mfa_code_rejected", extra={"user_id": user.id, "context": "enrol"}
        )
        raise InvalidMfaCodeError("invalid_mfa_code")

    mfa.enabled_at = datetime.now(timezone.utc)
    clear_failures(mfa)
    codes = await replace_recovery_codes(session, user.id)

    revoke = delete(RefreshToken).where(
        RefreshToken.user_id == user.id  # pyright: ignore[reportArgumentType]
    )
    if keep_session_id is not None:
        revoke = revoke.where(
            RefreshToken.id != keep_session_id  # pyright: ignore[reportArgumentType]
        )
        # This session just proved the code: it stays usable under MFA.
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.id == keep_session_id,  # pyright: ignore[reportArgumentType]
                RefreshToken.user_id == user.id,  # pyright: ignore[reportArgumentType]
            )
            .values(mfa_verified=True)
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
    await notify_mfa_event(session, user.email, MfaEvent.ENROLLED, ip=client_ip)
    logger.info("mfa_enrolled", extra={"user_id": user.id, "ip": client_ip})
    return codes


async def regenerate_recovery_codes(
    session: AsyncSession, user: User, code: str, *, client_ip: str | None = None
) -> list[str]:
    """Replace all recovery codes; requires a current TOTP code.

    The code counts toward the account lock like a login code: a stolen
    session must not get unlimited guesses at minting lasting recovery codes.
    """
    assert user.id is not None
    mfa = await get_user_mfa(session, user.id)
    if mfa is None or mfa.enabled_at is None:
        raise MfaNotEnrolledError("mfa_not_enrolled")
    now = datetime.now(timezone.utc)
    ensure_not_locked(mfa, now)
    if not await check_totp(session, mfa, code, now):
        locked = await record_failed_code(
            user.id, user.email, client_ip, context="regenerate"
        )
        raise locked or InvalidMfaCodeError("invalid_mfa_code")
    clear_failures(mfa)
    codes = await replace_recovery_codes(session, user.id)
    await record_audit_event(
        session,
        actor_user_id=user.id,
        action="mfa_recovery_codes_regenerated",
        target_type="User",
        target_id=user.id,
        ip_address=client_ip,
    )
    await notify_mfa_event(
        session, user.email, MfaEvent.RECOVERY_CODES_REGENERATED, ip=client_ip
    )
    return codes


async def mfa_status(session: AsyncSession, user_id: int) -> tuple[bool, int]:
    """(MFA enabled, unused recovery codes)."""
    if not await is_mfa_enabled(session, user_id):
        return False, 0
    return True, await remaining_recovery_codes(session, user_id)
