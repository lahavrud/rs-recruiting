"""Session listing and revocation endpoints — available to all authenticated users."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_user
from src.core.infrastructure.limiter import get_limiter
from src.core.infrastructure.security import hash_token
from src.core.infrastructure.transactions import transactional
from src.models import RefreshToken, User
from src.schemas.auth import SessionRead

logger = logging.getLogger(__name__)

limiter = get_limiter()
_REFRESH_COOKIE = "refresh_token"

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/sessions", response_model=list[SessionRead])
@limiter.limit("60/minute")
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SessionRead]:
    """List active (non-expired) sessions for the current user.

    The session whose refresh-token cookie matches the current request is
    marked ``is_current=True`` so the client can distinguish it.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(RefreshToken)
        .where(
            RefreshToken.user_id == current_user.id,  # type: ignore[arg-type]
            RefreshToken.expires_at > now,  # type: ignore[operator]
        )
        .order_by(RefreshToken.created_at.desc())
    )
    tokens = list(result.scalars().all())

    current_hash: str | None = None
    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    if raw_refresh:
        current_hash = hash_token(raw_refresh)

    return [
        SessionRead(
            id=t.id,  # type: ignore[arg-type]
            created_at=t.created_at,
            expires_at=t.expires_at,
            user_agent=t.user_agent,
            is_current=(current_hash is not None and t.token_hash == current_hash),
        )
        for t in tokens
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def revoke_session(
    request: Request,
    session_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Revoke a specific session by its DB id.

    Returns 404 when the session does not exist or belongs to another user —
    the two cases are intentionally indistinguishable to avoid oracle attacks.
    """
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.id == session_id,  # type: ignore[arg-type]
            RefreshToken.user_id == current_user.id,  # type: ignore[arg-type]
        )
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="session_not_found",
        )

    # Delete the row directly — no UsedRefreshToken entry.
    # If the revoked browser tries to refresh, it gets db_token=None → 401 (not
    # the "replay" path), so _nuke_user_refresh_tokens is never triggered and
    # other sessions are not affected.
    async with transactional(session):
        await session.delete(token)

    logger.info(
        "session_revoked",
        extra={"user_id": str(current_user.id), "session_id": session_id},
    )


@router.delete("/sessions", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def revoke_all_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Revoke all sessions for the current user (log out everywhere)."""
    async with transactional(session):
        result = await session.execute(
            select(RefreshToken.id).where(
                RefreshToken.user_id == current_user.id  # type: ignore[arg-type]
            )
        )
        count = len(result.scalars().all())
        await session.execute(
            sa_delete(RefreshToken).where(
                RefreshToken.user_id == current_user.id  # type: ignore[arg-type]
            )
        )

    logger.info(
        "all_sessions_revoked",
        extra={"user_id": str(current_user.id), "session_count": count},
    )
