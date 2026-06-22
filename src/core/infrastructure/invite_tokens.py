"""DB-backed invite token management for gated company registration."""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import hash_token
from src.services.exceptions import InvalidInviteTokenError

TOKEN_TTL_SECONDS = 2 * 60 * 60  # 2 hours


async def generate_invite_token() -> tuple[str, str, datetime]:
    """Generate a cryptographically secure token.

    Returns (raw_token, token_hash, expires_at). Only the hash is stored in
    the DB; the raw token is sent in the email link.
    """
    raw = secrets.token_urlsafe(32)
    token_hash = hash_token(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_TTL_SECONDS)
    return raw, token_hash, expires_at


async def validate_invite_token(token: str, session: AsyncSession) -> None:
    """Raise InvalidInviteTokenError if the token is not usable.

    Checks DB for a PENDING record whose expiry has not passed.
    """
    from src.enums import InviteTokenStatus
    from src.models import InviteToken

    result = await session.execute(
        select(InviteToken).where(
            InviteToken.token_hash == hash_token(token)  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
        )
    )
    record = result.scalar_one_or_none()
    if record is None or record.status != InviteTokenStatus.PENDING:
        raise InvalidInviteTokenError("Invite token is invalid or has expired")
    if record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise InvalidInviteTokenError("Invite token is invalid or has expired")
