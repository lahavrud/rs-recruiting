"""Admin endpoints for candidate management."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.infrastructure.dependencies import client_ip, get_current_admin
from rs_api.infrastructure.error_handling import service_exception_to_http
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    CursorPage,
)
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.core.services.storage import get_storage_provider
from rs_shared.models import User
from rs_shared.schemas import (
    CandidateActivityEvent,
    CandidateAdminRead,
    CandidateJobMatchRead,
)
from rs_shared.services.admin.candidates import (
    admin_tombstone_candidate,
    get_candidate,
    get_candidate_job_matches,
    list_candidate_activity,
    list_candidates,
)
from rs_shared.services.exceptions import (
    CandidateAlreadyDeletedError,
    CandidateNotFoundError,
    InvalidCursorError,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/candidates", response_model=CursorPage[CandidateAdminRead])
async def get_candidates(
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    q: str | None = Query(default=None, max_length=255),
    sort: Literal["name", "created_at", "score"] = Query(default="created_at"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    job_id: int | None = Query(default=None),
    has_account: bool | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[CandidateAdminRead]:
    """List candidate profiles, sorted by `sort`/`order`, cursor-paginated.

    `q` filters by name/email/phone (case-insensitive substring).
    `sort=score` ranks candidates by cosine similarity to `job_id`'s embedding.
    `has_account` filters by account presence (`user_id NOT NULL`).
    `include_deleted` (default false) controls whether tombstoned rows appear.
    """
    try:
        return await list_candidates(
            session,
            cursor=cursor,
            limit=limit,
            q=q,
            sort=sort,
            order=order,
            job_id=job_id,
            has_account=has_account,
            include_deleted=include_deleted,
        )
    except InvalidCursorError as exc:
        raise service_exception_to_http(exc) from exc


@router.get("/candidates/{candidate_id}", response_model=CandidateAdminRead)
async def get_candidate_endpoint(
    candidate_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CandidateAdminRead:
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
    """Tombstone a candidate: scrub PII, delete linked User, preserve applications.

    Returns 409 if the candidate is already tombstoned.
    """
    storage = get_storage_provider()
    try:
        async with transactional(session):
            await admin_tombstone_candidate(
                candidate_id,
                session,
                storage=storage,
                actor_user_id=current_admin.id,
                ip_address=client_ip(request),
            )
    except (CandidateNotFoundError, CandidateAlreadyDeletedError) as e:
        raise service_exception_to_http(e) from e
