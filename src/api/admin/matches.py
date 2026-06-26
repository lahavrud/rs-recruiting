"""Admin global match feed endpoint."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_admin
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.transactions import transactional
from src.models import User
from src.schemas import (
    ApplicationRead,
    ApplicationWithDetails,
    GlobalMatchRead,
    MatchSuggestionActionRequest,
)
from src.services.admin.matches import (
    dismiss_match,
    get_global_matches,
    get_hot_applications,
    push_match,
)
from src.services.exceptions import ApplicationAlreadyExistsError

router = APIRouter(prefix="/api/admin", tags=["admin"])

_MAX_LIMIT = 50


@router.get("/matches", response_model=list[GlobalMatchRead])
async def get_admin_matches(
    limit: int = Query(default=20, ge=1, le=_MAX_LIMIT),
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[GlobalMatchRead]:
    """AI suggestion feed — pairs with no application or prior admin action."""
    return await get_global_matches(session, limit=limit)


@router.get("/matches/hot", response_model=list[ApplicationWithDetails])
async def get_hot_matches(
    limit: int = Query(default=10, ge=1, le=20),
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[ApplicationWithDetails]:
    """High-score NEW applications — existing pipeline leads ranked by AI match."""
    return await get_hot_applications(session, limit=limit)


@router.post(
    "/matches/push",
    response_model=ApplicationRead,
    status_code=status.HTTP_201_CREATED,
)
async def push_match_endpoint(
    body: MatchSuggestionActionRequest,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> ApplicationRead:
    """Create an application from an AI match suggestion (admin-initiated)."""
    try:
        async with transactional(session):
            return await push_match(
                body.candidate_id,
                body.job_id,
                body.score,
                current_admin.id,  # type: ignore[arg-type]
                session,
            )
    except ApplicationAlreadyExistsError as exc:
        raise service_exception_to_http(exc) from exc


@router.post("/matches/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_match_endpoint(
    body: MatchSuggestionActionRequest,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Dismiss an AI match suggestion — permanently excludes it from the feed."""
    async with transactional(session):
        await dismiss_match(
            body.candidate_id,
            body.job_id,
            body.score,
            current_admin.id,  # type: ignore[arg-type]
            session,
        )
