"""TOTP code checks and recovery codes: the primitives behind ``mfa.py``.

Kept apart so ``mfa.py`` holds the flows (enrolment, login challenge) and this
module holds the parts with sharp edges: constant-time code comparison, the
±1-step skew window, the atomic replay claim, and recovery-code hashing.
"""

import hmac
import logging
import secrets
from datetime import datetime, timezone

import pyotp
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import (
    decrypt_mfa_secret,
    hash_mfa_recovery_code,
)
from rs_shared.models import MfaRecoveryCode, UserMfa

logger = logging.getLogger(__name__)

RECOVERY_CODE_COUNT = 10
# Unambiguous lowercase alphabet (no 0/o, 1/l/i): codes get read off paper.
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
_RECOVERY_HALF = 5
# Accept the previous, current and next 30-second step (clock skew).
_SKEW_STEPS = 1
_TOTP_DIGITS = 6


def _matching_step(secret: str, code: str, now: datetime) -> int | None:
    """The time-step ``code`` is valid for (within skew), or None."""
    code = code.strip().replace(" ", "")
    if len(code) != _TOTP_DIGITS or not code.isdigit():
        return None
    totp = pyotp.TOTP(secret)
    current = totp.timecode(now)
    for step in range(current - _SKEW_STEPS, current + _SKEW_STEPS + 1):
        if hmac.compare_digest(totp.generate_otp(step), code):
            return step
    return None


async def _claim_step(
    session: AsyncSession, user_id: int, step: int, now: datetime
) -> bool:
    """Atomically advance ``last_used_step``; False if used or locked.

    The lock is re-checked here, in the same row-locking UPDATE: a burst of
    guesses that all passed the caller's lock check before the locking
    failure committed still can't land a code.
    """
    result = await session.execute(
        update(UserMfa)
        .where(
            UserMfa.user_id == user_id,  # pyright: ignore[reportArgumentType]
            UserMfa.last_used_step < step,  # pyright: ignore[reportArgumentType]
            or_(
                UserMfa.locked_until.is_(None),  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
                UserMfa.locked_until <= now,  # pyright: ignore[reportOptionalOperand, reportOperatorIssue]
            ),
        )
        .values(last_used_step=step)
        .returning(UserMfa.user_id)  # pyright: ignore[reportArgumentType]
    )
    return result.first() is not None


async def check_totp(
    session: AsyncSession, mfa: UserMfa, code: str, now: datetime | None = None
) -> bool:
    """True if ``code`` is valid now and its time-step was not used before."""
    try:
        secret = decrypt_mfa_secret(mfa.secret_encrypted)
    except ValueError:
        # MFA_ENCRYPTION_KEY changed under the stored secret: only the
        # break-glass reset (docs/runbooks/mfa-reset.md) gets this user back in.
        logger.critical("mfa_secret_undecryptable", extra={"user_id": mfa.user_id})
        raise
    now = now or datetime.now(timezone.utc)
    step = _matching_step(secret, code, now)
    return step is not None and await _claim_step(session, mfa.user_id, step, now)


def _normalize_recovery_code(code: str) -> str:
    return code.strip().lower().replace("-", "").replace(" ", "")


def _new_recovery_code() -> str:
    chars = "".join(
        secrets.choice(_RECOVERY_ALPHABET) for _ in range(2 * _RECOVERY_HALF)
    )
    return f"{chars[:_RECOVERY_HALF]}-{chars[_RECOVERY_HALF:]}"


async def replace_recovery_codes(session: AsyncSession, user_id: int) -> list[str]:
    """Delete the user's codes and issue a fresh set; returns the raw codes."""
    await session.execute(
        delete(MfaRecoveryCode).where(
            MfaRecoveryCode.user_id == user_id  # pyright: ignore[reportArgumentType]
        )
    )
    codes = [_new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    for code in codes:
        session.add(
            MfaRecoveryCode(
                user_id=user_id,
                code_hash=hash_mfa_recovery_code(_normalize_recovery_code(code)),
            )
        )
    await session.flush()
    return codes


async def consume_recovery_code(session: AsyncSession, user_id: int, code: str) -> bool:
    """Mark one unused recovery code used; False if none matched."""
    result = await session.execute(
        update(MfaRecoveryCode)
        .where(
            MfaRecoveryCode.user_id == user_id,  # pyright: ignore[reportArgumentType]
            MfaRecoveryCode.code_hash  # pyright: ignore[reportArgumentType]
            == hash_mfa_recovery_code(_normalize_recovery_code(code)),
            MfaRecoveryCode.used_at.is_(None),  # type: ignore[union-attr]
        )
        .values(used_at=datetime.now(timezone.utc))
        .returning(MfaRecoveryCode.id)  # pyright: ignore[reportArgumentType]
    )
    return result.first() is not None


async def remaining_recovery_codes(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(MfaRecoveryCode)
        .where(
            MfaRecoveryCode.user_id == user_id,  # pyright: ignore[reportArgumentType]
            MfaRecoveryCode.used_at.is_(None),  # type: ignore[union-attr]
        )
    )
    return result.scalar_one()
