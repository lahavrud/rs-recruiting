"""Authenticated in-session password change endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_user
from src.core.infrastructure.limiter import get_limiter
from src.core.infrastructure.transactions import transactional
from src.models import User
from src.schemas import ChangePasswordRequest
from src.services.auth.password_change import change_user_password
from src.services.exceptions import InvalidCredentialsError

# `/auth/me` namespace — role-agnostic. Sprint 11 candidates use this; the
# pattern is open to admin/company self-service down the road.
router = APIRouter(prefix="/auth/me", tags=["auth"])
limiter = get_limiter()

_REFRESH_COOKIE = "refresh_token"


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/hour")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Change the authenticated user's password.

    Wrong ``current_password`` → 401. On success, every other refresh
    token for this user is revoked; the cookie carrying the current
    session is preserved so the request that submitted the change
    continues working.
    """
    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    try:
        async with transactional(session):
            await change_user_password(
                user,
                body.current_password,
                body.new_password,
                raw_refresh,
                session,
            )
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="current_password_incorrect",
        ) from e
