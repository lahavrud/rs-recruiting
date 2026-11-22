"""Admin endpoints for company invite-token management."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.infrastructure.dependencies import client_ip, get_current_admin
from rs_api.infrastructure.error_handling import service_exception_to_http
from rs_api.infrastructure.limiter import get_limiter
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    CursorPage,
)
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.enums import InviteTokenStatus
from rs_shared.models import User
from rs_shared.schemas import InviteTokenCreate, InviteTokenRead
from rs_shared.services.admin.invites import (
    create_invite,
    delete_invite,
    list_invites,
    resend_invite,
    revoke_invite,
)
from rs_shared.services.exceptions import (
    EmailAlreadyExistsError,
    InvalidCursorError,
    InviteAlreadyRevokedError,
    InviteNotFoundError,
    InvitePendingForEmailError,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])
limiter = get_limiter()


@router.post(
    "/companies/invite",
    response_model=InviteTokenRead,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/hour")
async def create_company_invite(
    request: Request,
    data: InviteTokenCreate,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> InviteTokenRead:
    """Generate a single-use invite token and send it via email."""
    if current_admin.id is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    try:
        async with transactional(session):
            return await create_invite(current_admin.id, data, session)
    except (InvitePendingForEmailError, EmailAlreadyExistsError) as e:
        raise service_exception_to_http(e) from e


@router.get("/companies/invites", response_model=CursorPage[InviteTokenRead])
async def get_company_invites(
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    status: InviteTokenStatus | None = None,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[InviteTokenRead]:
    """List invite tokens, newest first. Expired tokens are marked before returning."""
    try:
        return await list_invites(session, cursor=cursor, limit=limit, status=status)
    except InvalidCursorError as exc:
        raise service_exception_to_http(exc) from exc


@router.post(
    "/companies/invites/{token_id}/revoke", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_company_invite(
    request: Request,
    token_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Revoke a pending invite token (status=REVOKED; row preserved for audit)."""
    try:
        async with transactional(session):
            await revoke_invite(
                token_id,
                session,
                actor_user_id=current_admin.id,
                ip_address=client_ip(request),
            )
    except (InviteNotFoundError, InviteAlreadyRevokedError) as e:
        raise service_exception_to_http(e) from e


@router.delete("/companies/invites/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_invite(
    request: Request,
    token_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Hard-delete an invite row regardless of status."""
    try:
        async with transactional(session):
            await delete_invite(
                token_id,
                session,
                actor_user_id=current_admin.id,
                ip_address=client_ip(request),
            )
    except InviteNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.post(
    "/companies/invites/{token_id}/resend",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("20/hour")
async def resend_company_invite(
    request: Request,
    token_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Regenerate and resend an invite email for an existing invite record."""
    try:
        async with transactional(session):
            await resend_invite(
                token_id,
                session,
                actor_user_id=current_admin.id,
                ip_address=client_ip(request),
            )
    except (InviteNotFoundError, InviteAlreadyRevokedError) as e:
        raise service_exception_to_http(e) from e
