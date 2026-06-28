"""Session listing and revocation endpoints — available to all authenticated users."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_user
from src.core.infrastructure.transactions import transactional
from src.models import RefreshToken, UsedRefreshToken, User
from src.schemas.auth import SessionRead

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/sessions", response_model=list[SessionRead])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[RefreshToken]:
    """List active (non-expired) sessions for the current user."""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(RefreshToken)
        .where(
            RefreshToken.user_id == current_user.id,  # type: ignore[arg-type]
            RefreshToken.expires_at > now,  # type: ignore[operator]
        )
        .order_by(RefreshToken.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
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

    async with transactional(session):
        session.add(
            UsedRefreshToken(
                token_hash=token.token_hash,
                user_id=token.user_id,
                expires_at=token.expires_at,
            )
        )
        await session.delete(token)


@router.delete("/sessions", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Revoke all sessions for the current user (log out everywhere).

    Each token hash is moved to UsedRefreshToken so any in-flight refresh
    attempt against a rotated token is still caught by replay detection.
    """
    async with transactional(session):
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == current_user.id  # type: ignore[arg-type]
            )
        )
        tokens = list(result.scalars().all())
        for token in tokens:
            session.add(
                UsedRefreshToken(
                    token_hash=token.token_hash,
                    user_id=token.user_id,
                    expires_at=token.expires_at,
                )
            )
        await session.execute(
            sa_delete(RefreshToken).where(
                RefreshToken.user_id == current_user.id  # type: ignore[arg-type]
            )
        )
