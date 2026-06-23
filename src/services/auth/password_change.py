"""In-session password change.

Role-agnostic. Distinct from the forgot-password flow:
* this requires the existing session's access token AND the user's current
  password (defense against session-hijack-then-takeover);
* it revokes every refresh token except the current one, so leaked
  credentials can no longer ride parallel sessions.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import (
    get_password_hash,
    hash_token,
    is_password_valid,
)
from src.models import RefreshToken, User
from src.services.exceptions import InvalidCredentialsError
from src.services.utils.audit import record_audit_event

logger = logging.getLogger(__name__)


async def change_user_password(
    user: User,
    current_password: str,
    new_password: str,
    current_refresh_token: str | None,
    session: AsyncSession,
) -> None:
    """Replace the user's password + revoke other refresh tokens.

    Args:
        user: authenticated user (from ``get_current_user``).
        current_password: plain-text current password to verify.
        new_password: plain-text new password (caller has already
            run the complexity validator).
        current_refresh_token: the raw refresh token from the request's
            HttpOnly cookie. When supplied, the matching ``RefreshToken``
            row is preserved so the current session stays valid; every
            other row for this user is revoked.
        session: db session (caller owns the transaction).

    Raises:
        InvalidCredentialsError: when current_password doesn't verify.
    """
    # Re-fetch in the request's session so mutations get persisted. The
    # ``user`` passed in via the dep may be detached (e.g. cached identity
    # object from a previous request, or test-override stubs).
    persisted = (
        await session.execute(
            select(User).where(User.id == user.id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one()

    if not is_password_valid(current_password, persisted.hashed_password):
        raise InvalidCredentialsError("current_password_incorrect")

    persisted.hashed_password = get_password_hash(new_password)

    # Drop every refresh token for this user except the one carrying the
    # current session's cookie — the user stays logged in here, every
    # other parallel session is forcibly signed out. Delete-on-rotate is
    # the project-wide refresh-token cleanup policy; rows no longer linger
    # with ``is_revoked = True``.
    query = delete(RefreshToken).where(
        RefreshToken.user_id == persisted.id,  # pyright: ignore[reportArgumentType]
    )
    if current_refresh_token:
        query = query.where(
            RefreshToken.token_hash != hash_token(current_refresh_token)
        )
    await session.execute(query)

    await record_audit_event(
        session,
        actor_user_id=persisted.id,
        action="password_changed",
        target_type="user",
        target_id=persisted.id,
        detail=f"changed_at={datetime.now(timezone.utc).isoformat()}",
    )
