"""Password-reset endpoints (forgot-password + reset-password)."""

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.infrastructure.error_handling import service_exception_to_http
from rs_api.infrastructure.limiter import get_limiter
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.schemas import ForgotPasswordRequest, ResetPasswordRequest
from rs_shared.services.auth.password_reset import (
    request_password_reset,
    reset_password,
    validate_password_reset_token,
)
from rs_shared.services.exceptions import InvalidPasswordResetTokenError

limiter = get_limiter()
router = APIRouter(prefix="/auth", tags=["auth"])

_GENERIC_FORGOT_RESPONSE = {
    "message": "אם הכתובת רשומה במערכת, ישלח אליה קישור לאיפוס סיסמה."
}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/hour")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Always returns the same response — never reveals whether the email exists.

    The IP-level rate limit (`5/hour`) covers enumeration-via-many-emails;
    a per-email limit (a DB row count) inside `request_password_reset`
    protects a single victim's inbox from spam.
    """
    async with transactional(session):
        await request_password_reset(body.email, session)
    return _GENERIC_FORGOT_RESPONSE


@router.get("/reset-password/validate", status_code=status.HTTP_200_OK)
@limiter.limit("30/hour")
async def validate_reset_token(
    request: Request,
    token: str = Query(..., min_length=1, max_length=200),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Check whether a reset token is still usable, without consuming it.

    Lets the frontend show the invalid-token page immediately on load
    rather than after the user fills in a new password.  Same 400 mapping
    as the consume endpoint, so the page can branch on status alone.
    """
    try:
        await validate_password_reset_token(token, session)
    except InvalidPasswordResetTokenError as e:
        raise service_exception_to_http(e) from e
    return {"valid": True}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit("10/hour")
async def reset_password_endpoint(
    request: Request,
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Consume a reset token and set a new password."""
    try:
        async with transactional(session):
            await reset_password(body.token, body.new_password, session)
    except InvalidPasswordResetTokenError as e:
        raise service_exception_to_http(e) from e
    return {"message": "הסיסמה עודכנה בהצלחה"}
