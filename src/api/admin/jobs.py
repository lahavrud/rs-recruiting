"""Admin endpoints for job management — CRUD and approval workflow."""

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_admin
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.limiter import get_limiter
from src.core.infrastructure.pagination import DEFAULT_LIMIT, MAX_LIMIT, CursorPage
from src.core.infrastructure.transactions import transactional
from src.enums import JobStatus
from src.models import User
from src.schemas import (
    JobAdminCreate,
    JobAdminUpdate,
    JobCandidateMatchRead,
    JobContactEmailRequest,
    JobRead,
)
from src.services.admin.jobs import (
    admin_create_job,
    delete_job,
    get_job_candidate_matches,
    list_jobs,
    update_job,
)
from src.services.admin.jobs_workflow import (
    approve_job,
    contact_job,
    list_pending_jobs,
    reject_job,
)
from src.services.company.jobs import get_job
from src.services.exceptions import (
    CompanyNotFoundError,
    InvalidCursorError,
    JobNotFoundError,
    JobNotPendingError,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])
limiter = get_limiter()


@router.get("/jobs/pending", response_model=CursorPage[JobRead])
async def get_pending_jobs(
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[JobRead]:
    """List PENDING_APPROVAL job postings, cursor-paginated."""
    return await list_pending_jobs(session, cursor=cursor, limit=limit)


@router.get("/jobs", response_model=CursorPage[JobRead])
async def get_jobs(
    status: JobStatus | None = None,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[JobRead]:
    """List jobs across all statuses, newest first, cursor-paginated."""
    try:
        return await list_jobs(session, status=status, cursor=cursor, limit=limit)
    except InvalidCursorError as exc:
        raise service_exception_to_http(exc) from exc


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def create_job(
    data: JobAdminCreate,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Create a job directly under an existing company profile.

    Status defaults to PUBLISHED — admin-created jobs skip the approval flow.
    """
    try:
        async with transactional(session):
            return await admin_create_job(data, session)
    except CompanyNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.get("/jobs/{job_id}", response_model=JobRead)
async def get_job_endpoint(
    job_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Fetch a single job by id, regardless of status."""
    try:
        return await get_job(job_id, session)
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.get(
    "/jobs/{job_id}/candidate-matches",
    response_model=list[JobCandidateMatchRead],
)
async def get_job_candidate_matches_endpoint(
    job_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[JobCandidateMatchRead]:
    """Ranked resume-match results for a job, best score first."""
    try:
        return await get_job_candidate_matches(job_id, session)
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.put("/jobs/{job_id}", response_model=JobRead)
async def update_job_endpoint(
    job_id: int,
    data: JobAdminUpdate,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Partially update any field on a job at any status."""
    try:
        async with transactional(session):
            return await update_job(
                job_id, data, session, actor_user_id=current_admin.id
            )
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_endpoint(
    job_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Hard-delete a job and cascade through its applications."""
    try:
        async with transactional(session):
            await delete_job(job_id, session)
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.post(
    "/jobs/{job_id}/approve", response_model=JobRead, status_code=status.HTTP_200_OK
)
async def approve_job_posting(
    job_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Approve a pending job; sets status to PUBLISHED and notifies the company."""
    try:
        async with transactional(session):
            return await approve_job(job_id, session, actor_user_id=current_admin.id)
    except (JobNotFoundError, JobNotPendingError) as e:
        raise service_exception_to_http(e) from e


@router.post("/jobs/{job_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_job_posting(
    job_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Reject a pending job; sets status to CLOSED and notifies the company."""
    try:
        async with transactional(session):
            await reject_job(job_id, session, actor_user_id=current_admin.id)
    except (JobNotFoundError, JobNotPendingError) as e:
        raise service_exception_to_http(e) from e


@router.post("/jobs/{job_id}/contact", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/hour")
async def contact_job_posting(
    request: Request,
    job_id: int,
    body: JobContactEmailRequest,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Send a contextual email to the company that owns a job posting."""
    try:
        await contact_job(job_id, body.admin_note, session)
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e
