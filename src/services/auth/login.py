"""Login authentication logic: credential validation and lockout tracking.

Token issuance and rotation live in ``session.py``.
"""

import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import get_password_hash, is_password_valid
from src.models import ActivationToken, User
from src.services.exceptions import (
    AccountLockedError,
    InvalidCredentialsError,
    PendingActivationError,
    PendingApprovalError,
)

logger = logging.getLogger(__name__)

_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_DURATION = timedelta(minutes=15)

# Pre-computed once at module load so authenticate_user takes ~100 ms
# regardless of whether the email exists, preventing timing-based email
# enumeration (comparing branch latency distinguishes "not found" from
# "wrong password" without this equalisation).
_DUMMY_HASH: str = get_password_hash("dummy-fixed-for-timing")


def _email_prefix(email: str) -> str:
    """First two chars of the local part — loggable without storing PII."""
    local = email.split("@")[0]
    return f"{local[:2]}***"


def _check_lockout(user: User, client_ip: str | None = None) -> None:
    """Raise AccountLockedError if the user is currently locked out."""
    if user.locked_until is None:
        return
    now = datetime.now(timezone.utc)
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until > now:
        ttl = (locked_until - now).total_seconds()
        logger.warning(
            "login_lockout_hit",
            extra={
                "email_prefix": _email_prefix(user.email),
                "ttl_s": int(ttl),
                "ip": client_ip,
            },
        )
        raise AccountLockedError(minutes_remaining=math.ceil(ttl / 60))


async def _record_failed_attempt(
    user_id: int, email: str, client_ip: str | None = None
) -> None:
    """Atomically increment failed_login_attempts; lock the account at threshold.

    Uses its own DB session so the write persists even when the calling
    request raises InvalidCredentialsError and its session rolls back.
    The UPDATE is a single atomic SQL statement — no read-modify-write race.
    """
    from src.core.infrastructure.database import async_session as _session_factory

    async with _session_factory() as session:
        await session.execute(
            update(User)
            .where(User.id == user_id)  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
            .values(failed_login_attempts=User.failed_login_attempts + 1)
        )
        await session.flush()

        result = await session.execute(
            select(User.failed_login_attempts).where(User.id == user_id)  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
        )
        count = result.scalar_one()

        if count >= _MAX_FAILED_ATTEMPTS:
            await session.execute(
                update(User)
                .where(User.id == user_id)  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
                .values(
                    failed_login_attempts=0,
                    locked_until=datetime.now(timezone.utc) + _LOCKOUT_DURATION,
                )
            )
            logger.warning(
                "login_account_locked",
                extra={"email_prefix": _email_prefix(email), "ip": client_ip},
            )
        else:
            logger.warning(
                "login_failed",
                extra={
                    "email_prefix": _email_prefix(email),
                    "attempt": count,
                    "ip": client_ip,
                },
            )

        await session.commit()


async def _clear_failed_attempts(user_id: int) -> None:
    """Reset lockout state on successful login or password reset."""
    from src.core.infrastructure.database import async_session as _session_factory

    async with _session_factory() as session:
        await session.execute(
            update(User)
            .where(User.id == user_id)  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
            .values(failed_login_attempts=0, locked_until=None)
        )
        await session.commit()


async def authenticate_user(
    email: str,
    password: str,
    session: AsyncSession,
    client_ip: str | None = None,
) -> User:
    """Authenticate a user by email and password.

    Checks for account lockout before attempting credential validation.
    Tracks failed attempts and locks the account after too many failures.
    """
    email = email.lower().strip()
    result = await session.execute(
        select(User).where(User.email == email)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one_or_none()
    if not user:
        is_password_valid(password, _DUMMY_HASH)  # equalise timing
        logger.warning("login_email_not_found", extra={"ip": client_ip})
        raise InvalidCredentialsError("Incorrect email or password")

    # Run bcrypt before the lockout check so every code path where the email
    # exists takes ~100 ms, preventing timing from distinguishing "locked" from
    # "wrong password" and leaking that the email is registered.
    password_ok = is_password_valid(password, user.hashed_password)
    _check_lockout(user, client_ip)

    if not password_ok:
        assert user.id is not None
        await _record_failed_attempt(user.id, email, client_ip)
        raise InvalidCredentialsError("Incorrect email or password")

    if not user.is_active:
        # Distinguish: has a pending activation token → admin approved but company
        # hasn't clicked the link yet.  No token → still awaiting admin review.
        activation_result = await session.execute(
            select(ActivationToken).where(
                ActivationToken.user_id == user.id,  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
                ActivationToken.used == False,  # noqa: E712
            )
        )
        if activation_result.scalar_one_or_none() is not None:
            raise PendingActivationError("account_pending_activation")
        raise PendingApprovalError("account_pending_approval")

    assert user.id is not None
    await _clear_failed_attempts(user.id)
    return user
