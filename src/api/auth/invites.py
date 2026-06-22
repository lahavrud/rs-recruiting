"""Public invite token endpoints (no authentication required)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.invite_tokens import validate_invite_token
from src.core.infrastructure.security import hash_token
from src.models import InviteToken
from src.schemas import InviteMetadataPublic
from src.services.exceptions import InvalidInviteTokenError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/invite/{token}", response_model=InviteMetadataPublic)
async def get_invite_metadata(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> InviteMetadataPublic:
    """Return public pre-fill data for a valid invite token."""
    try:
        await validate_invite_token(token, session)
    except InvalidInviteTokenError as e:
        raise service_exception_to_http(e) from e
    result = await session.execute(
        select(InviteToken).where(InviteToken.token_hash == hash_token(token))  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise service_exception_to_http(
            InvalidInviteTokenError(f"Invite token not found: {token}")
        )
    return InviteMetadataPublic.model_validate(record)
