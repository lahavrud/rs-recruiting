"""Admin endpoints for candidate management."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import client_ip, get_current_admin
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.pagination import DEFAULT_LIMIT, MAX_LIMIT, CursorPage
from src.core.infrastructure.transactions import transactional
from src.models import User
from src.schemas import (
    CandidateActivityEvent,
    CandidateJobMatchRead,
    CandidateProfileRead,
)
from src.services.admin.candidates import (
    delete_candidate,
    get_candidate,
    get_candidate_job_matches,
    list_candidate_activity,
    list_candidates,
)
from src.services.exceptions import CandidateNotFoundError, InvalidCursorError

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/candidates", response_model=CursorPage[CandidateProfileRead])
async def get_candidates(
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    q: str | None = Query(default=None, max_length=255),
    sort: Literal["name", "created_at"] = Query(default="created_at"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[CandidateProfileRead]:
    """List candidate profiles, sorted by `sort`/`order`, cursor-paginated.

    `q`, when given, filters by name/email/phone (case-insensitive substring).
    """
    try:
        return await list_candidates(
            session, cursor=cursor, limit=limit, q=q, sort=sort, order=order
        )
    except InvalidCursorError as exc:
        raise service_exception_to_http(exc) from exc


@router.get("/candidates/{candidate_id}", response_model=CandidateProfileRead)
async def get_candidate_endpoint(
    candidate_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CandidateProfileRead:
    """Fetch a single candidate profile by id."""
    try:
        return await get_candidate(candidate_id, session)
    except CandidateNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.get(
    "/candidates/{candidate_id}/job-matches",
    response_model=list[CandidateJobMatchRead],
)
async def get_candidate_job_matches_endpoint(
    candidate_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[CandidateJobMatchRead]:
    """Ranked resume-match results for a candidate, best score first."""
    try:
        return await get_candidate_job_matches(candidate_id, session)
    except CandidateNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.get(
    "/candidates/{candidate_id}/activity",
    response_model=CursorPage[CandidateActivityEvent],
)
async def get_candidate_activity(
    candidate_id: int,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[CandidateActivityEvent]:
    """Activity timeline: audit rows for the candidate and their applications."""
    try:
        return await list_candidate_activity(
            candidate_id, session, cursor=cursor, limit=limit
        )
    except (CandidateNotFoundError, InvalidCursorError) as exc:
        raise service_exception_to_http(exc) from exc


@router.delete("/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate_endpoint(
    candidate_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Hard-delete a candidate and cascade through their applications."""
    try:
        async with transactional(session):
            await delete_candidate(
                candidate_id,
                session,
                actor_user_id=current_admin.id,
                ip_address=client_ip(request),
            )
    except CandidateNotFoundError as e:
        raise service_exception_to_http(e) from e
