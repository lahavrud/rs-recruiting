"""Self-service password reset.

Security model:
- Reset tokens are random 32-byte URL-safe strings; DB stores only their
  SHA-256 hash (mirrors `RefreshToken`).
- `forgot_password` MUST be indistinguishable for known and unknown emails:
  the caller always sees the same response, and the email send is deferred
  via `defer_after_commit` so timing differences from SMTP cannot leak.
- Per-email rate limit (3/hour) lives in Redis and protects victims from
  inbox-spam when the IP rate limit is wide-open.
- Successful reset revokes every refresh token for the user and clears any
  lockout state, so a leaked password can no longer ride existing sessions.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.security import (
    get_password_hash,
    hash_token,
)
from src.core.infrastructure.transactions import defer_after_commit
from src.core.tasks import enqueue_email_task
from src.models import PasswordResetToken, RefreshToken, User
from src.services.auth.login import _clear_failed_attempts
from src.services.exceptions import InvalidPasswordResetTokenError
from src.services.utils.audit import record_audit_event
from src.templates.email import build_password_reset_html

logger = logging.getLogger(__name__)

_RESET_TOKEN_TTL = timedelta(hours=1)
_EMAIL_RATE_LIMIT_WINDOW = timedelta(hours=1)
_EMAIL_RATE_LIMIT_MAX = 3


async def _per_email_rate_limit_ok(user_id: int, session: AsyncSession) -> bool:
    """Allow at most _EMAIL_RATE_LIMIT_MAX reset requests per user per hour.

    Counts existing PasswordResetToken rows in the last hour. A small window
    exists for parallel requests both reading count < MAX, but the per-IP
    slowapi limit covers the real abuse case at this volume.
    """
    window_start = datetime.now(timezone.utc) - _EMAIL_RATE_LIMIT_WINDOW
    result = await session.execute(
        select(func.count())
        .select_from(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
            PasswordResetToken.created_at > window_start,
        )
    )
    return result.scalar_one() < _EMAIL_RATE_LIMIT_MAX


async def request_password_reset(email: str, session: AsyncSession) -> None:
    """Issue a reset token + send email when the address belongs to a user.

    Silent on unknown emails. The caller always observes the same outcome.
    """
    cleaned = email.lower().strip()
    if not cleaned:
        return

    result = await session.execute(
        select(User).where(User.email == cleaned)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one_or_none()
    if user is None or user.id is None:
        return

    if not await _per_email_rate_limit_ok(user.id, session):
        # Silent skip — surface only via logs.  Returning here keeps the
        # endpoint response identical to the unknown-email branch and stops
        # an attacker from flooding the user's inbox.
        logger.info(
            "password_reset_rate_limited", extra={"email_hash": hash_token(cleaned)}
        )
        return

    raw_token = secrets.token_urlsafe(32)
    token_record = PasswordResetToken(
        token_hash=hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + _RESET_TOKEN_TTL,
        used=False,
    )
    session.add(token_record)

    reset_url = f"{settings.frontend_base_url}/reset-password?token={raw_token}"
    recipient = user.email
    html = build_password_reset_html(reset_url)
    plain = (
        "קיבלנו בקשה לאיפוס סיסמה לחשבון שלך ב-RS Recruiting.\n"
        f"להגדרת סיסמה חדשה: {reset_url}\n"
        "הקישור תקף ל-60 דקות.\n"
        "אם לא ביקשת איפוס סיסמה, ניתן להתעלם מההודעה."
    )
    defer_after_commit(
        lambda: enqueue_email_task(
            to=recipient,
            subject="איפוס סיסמה — RS Recruiting",
            body=plain,
            html_body=html,
        )
    )


async def _load_active_reset_token(
    raw_token: str, session: AsyncSession
) -> PasswordResetToken:
    """Load a reset token row only if it's still usable (not used / not expired)."""
    result = await session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(raw_token)  # pyright: ignore[reportArgumentType]
        )
    )
    record = result.scalar_one_or_none()
    if record is None or record.used:
        logger.warning(
            "password_reset_token_invalid", extra={"reason": "not_found_or_used"}
        )
        raise InvalidPasswordResetTokenError("הקישור אינו תקף או שכבר נעשה בו שימוש")
    if record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        logger.warning("password_reset_token_invalid", extra={"reason": "expired"})
        raise InvalidPasswordResetTokenError("פג תוקף הקישור")
    return record


async def validate_password_reset_token(raw_token: str, session: AsyncSession) -> None:
    """Raise if the token isn't usable; otherwise return.  Does NOT consume it.

    Used by the frontend to gate the reset-password form on a usable link —
    so a stale link goes straight to the error page instead of letting the
    user fill in a new password before discovering it.
    """
    await _load_active_reset_token(raw_token, session)


async def reset_password(
    raw_token: str, new_password: str, session: AsyncSession
) -> User:
    """Consume a reset token, set the new password, revoke all refresh tokens.

    Raises:
        InvalidPasswordResetTokenError: token missing, used, or expired.
    """
    result = await session.execute(
        select(PasswordResetToken, User)
        .join(User, User.id == PasswordResetToken.user_id)  # pyright: ignore[reportArgumentType]
        .where(PasswordResetToken.token_hash == hash_token(raw_token))  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
    )
    row = result.one_or_none()
    if row is None:
        logger.warning("password_reset_token_invalid", extra={"reason": "not_found"})
        raise InvalidPasswordResetTokenError("הקישור אינו תקף או שכבר נעשה בו שימוש")
    record, user = row
    if record.used:
        logger.warning("password_reset_token_invalid", extra={"reason": "already_used"})
        raise InvalidPasswordResetTokenError("הקישור אינו תקף או שכבר נעשה בו שימוש")
    if record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        logger.warning("password_reset_token_invalid", extra={"reason": "expired"})
        raise InvalidPasswordResetTokenError("פג תוקף הקישור")

    user.hashed_password = get_password_hash(new_password)
    record.used = True

    # Every parallel session for this user is wiped — a password reset
    # is the canonical "log everyone out" event. Delete instead of
    # mark-revoked; same security guarantee, no row accumulation.
    await session.execute(
        delete(RefreshToken).where(
            RefreshToken.user_id == user.id,  # pyright: ignore[reportArgumentType]
        )
    )

    await record_audit_event(
        session,
        actor_user_id=user.id,
        action="password_reset",
        target_type="user",
        target_id=user.id,
    )

    user_id = user.id
    defer_after_commit(lambda: _clear_failed_attempts(user_id))
    return user
