"""Company job endpoints — list, get, create, update, delete."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_company
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.pagination import DEFAULT_LIMIT, CursorPage
from src.core.infrastructure.transactions import transactional
from src.models import CompanyProfile, User
from src.schemas import JobCreate, JobRead, JobUpdate
from src.schemas.companies import (
    CompanyApplicationRead,
    CompanyApplicationStatusUpdate,
    CompanyJobRecommendationRead,
)
from src.services.company.jobs import (
    create_job,
    delete_job,
    get_job,
    get_job_recommendations,
    list_company_jobs,
    list_job_applications,
    update_application_status,
    update_job,
)
from src.services.exceptions import (
    ApplicationNotFoundError,
    CompanyNotFoundError,
    InvalidApplicationStatusTransitionError,
    JobCannotBeDeletedError,
    JobCannotBeUpdatedError,
    JobNotFoundError,
    JobNotOwnedByCompanyError,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/", response_model=CursorPage[JobRead])
async def get_company_jobs(
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[JobRead]:
    """List the current company's jobs, cursor-paginated."""
    user, company_profile = current_company
    return await list_company_jobs(
        company_profile.id, session, cursor=cursor, limit=limit
    )


@router.get("/{job_id}", response_model=JobRead)
async def get_job_posting(
    job_id: int,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Get a specific job posting owned by the current company."""
    user, company_profile = current_company
    try:
        job = await get_job(job_id, session)
        if job.company_id != company_profile.id:
            raise JobNotFoundError(f"Job with ID {job_id} not owned by company")
        return job
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.post("/", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def create_job_posting(
    job_data: JobCreate,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Create a new job posting (PENDING_APPROVAL). Requires company auth."""
    _, company_profile = current_company
    try:
        async with transactional(session):
            return await create_job(job_data, company_profile.id, session)
    except (CompanyNotFoundError, JobNotFoundError) as e:
        raise service_exception_to_http(e) from e


@router.put("/{job_id}", response_model=JobRead, status_code=status.HTTP_200_OK)
async def update_job_posting(
    job_id: int,
    job_data: JobUpdate,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> JobRead:
    """Update a job posting. Company owner only; PENDING_APPROVAL or PUBLISHED."""
    _, company_profile = current_company
    try:
        async with transactional(session):
            return await update_job(job_id, job_data, company_profile.id, session)
    except (JobNotFoundError, JobNotOwnedByCompanyError, JobCannotBeUpdatedError) as e:
        raise service_exception_to_http(e) from e


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_posting(
    job_id: int,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a job posting. Company owner only; PENDING_APPROVAL only."""
    _, company_profile = current_company
    try:
        async with transactional(session):
            await delete_job(job_id, company_profile.id, session)
    except (JobNotFoundError, JobNotOwnedByCompanyError, JobCannotBeDeletedError) as e:
        raise service_exception_to_http(e) from e


@router.get("/{job_id}/applications", response_model=list[CompanyApplicationRead])
async def get_job_applications(
    job_id: int,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> list[CompanyApplicationRead]:
    """List all applications for a job owned by the current company."""
    _, company_profile = current_company
    try:
        return await list_job_applications(job_id, company_profile.id, session)
    except (JobNotFoundError, JobNotOwnedByCompanyError) as e:
        raise service_exception_to_http(e) from e


@router.patch(
    "/{job_id}/applications/{app_id}/status",
    response_model=CompanyApplicationRead,
)
async def update_job_application_status(
    job_id: int,
    app_id: int,
    body: CompanyApplicationStatusUpdate,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> CompanyApplicationRead:
    """Update an application's status (HIRED or REJECTED only). Company owner only."""
    _, company_profile = current_company
    try:
        async with transactional(session):
            return await update_application_status(
                job_id, app_id, body.status, company_profile.id, session
            )
    except InvalidApplicationStatusTransitionError as e:
        raise service_exception_to_http(e) from e
    except (JobNotFoundError, ApplicationNotFoundError) as e:
        raise service_exception_to_http(e) from e
    except JobNotOwnedByCompanyError as e:
        raise service_exception_to_http(e) from e


@router.get(
    "/{job_id}/recommendations", response_model=list[CompanyJobRecommendationRead]
)
async def get_job_candidate_recommendations(
    job_id: int,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> list[CompanyJobRecommendationRead]:
    """AI-ranked candidate suggestions for a specific job owned by this company."""
    _, company_profile = current_company
    try:
        return await get_job_recommendations(job_id, company_profile.id, session)
    except (JobNotFoundError, JobNotOwnedByCompanyError) as e:
        raise service_exception_to_http(e) from e
