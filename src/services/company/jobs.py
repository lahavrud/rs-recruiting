"""Job service layer for business logic."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.core.infrastructure.transactions import defer_after_commit
from src.core.tasks import enqueue_email_task
from src.enums import JobStatus
from src.models import CompanyProfile, Job
from src.schemas import JobCreate, JobRead, JobUpdate
from src.services.admin.companies import get_all_admin_emails
from src.services.company._jobs_applications import (
    list_job_applications,
    update_application_status,
)
from src.services.company._jobs_recommendations import get_job_recommendations
from src.services.exceptions import (
    CompanyNotFoundError,
    JobCannotBeDeletedError,
    JobCannotBeUpdatedError,
    JobNotFoundError,
    JobNotOwnedByCompanyError,
)
from src.templates.email import build_job_updated_html, build_new_job_html

__all__ = [
    "create_job",
    "delete_job",
    "get_job",
    "get_job_recommendations",
    "list_company_jobs",
    "list_job_applications",
    "update_application_status",
    "update_job",
]


async def create_job(
    job_data: JobCreate, company_id: int, session: AsyncSession
) -> JobRead:
    """Always starts in PENDING_APPROVAL — companies cannot publish directly,
    so every posting goes through admin review first. Notifies all admins
    by email so the review queue doesn't rely on them polling the admin UI.

    Raises:
        CompanyNotFoundError: If company not found
    """
    company = await get_by_id_or_raise(
        session,
        CompanyProfile,
        company_id,
        lambda pk: CompanyNotFoundError(f"Company with ID {pk} not found"),
    )

    new_job = Job(
        company_id=company_id,
        title=job_data.title,
        short_description=job_data.short_description,
        description=job_data.description,
        requirements=[r.model_dump() for r in job_data.requirements],
        tags=list(job_data.tags),
        location=job_data.location,
        salary_min=job_data.salary_min,
        salary_max=job_data.salary_max,
        status=JobStatus.PENDING_APPROVAL,
    )
    session.add(new_job)
    await session.flush()

    admin_emails = await get_all_admin_emails(session)
    if admin_emails:
        from src.core.infrastructure.config import settings

        admin_url = f"{settings.frontend_base_url}/login?redirect=/admin/jobs"
        _plain = f"משרה חדשה ממתינה לאישור: {new_job.title} ({company.name})"
        _html = build_new_job_html(
            job_title=new_job.title,
            company_name=company.name or "",
            location=new_job.location,
            job_id=new_job.id or 0,
            admin_url=admin_url,
        )
        defer_after_commit(
            lambda: enqueue_email_task(
                to=admin_emails,
                subject="משרה חדשה ממתינה לאישור – RS Recruiting",
                body=_plain,
                html_body=_html,
            )
        )

    return JobRead.model_validate(new_job)


async def get_job(job_id: int, session: AsyncSession) -> JobRead:
    job = await get_by_id_or_raise(
        session, Job, job_id, lambda pk: JobNotFoundError(f"Job with ID {pk} not found")
    )
    return JobRead.model_validate(job)


async def list_company_jobs(
    company_id: int,
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[JobRead]:
    page_size = clamp_limit(limit)
    query = apply_cursor(
        select(Job).where(Job.company_id == company_id),  # pyright: ignore[reportArgumentType]
        sort_col=Job.created_at,  # pyright: ignore[reportArgumentType]
        id_col=Job.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
    )
    rows = list((await session.execute(query)).scalars().all())
    return build_cursor_page(
        rows,
        serializer=JobRead.model_validate,
        cursor_key=lambda j: (j.created_at, j.id),
        limit=page_size,
    )


async def update_job(
    job_id: int,
    job_data: JobUpdate,
    company_id: int,
    session: AsyncSession,
) -> JobRead:
    """Blocked once a job is CLOSED — a closed posting is final and shouldn't
    be reanimated by an edit. `status` itself is excluded from the patch
    since only admins drive the approval workflow; a company silently
    flipping its own status would bypass review. Admins are re-notified by
    email on every edit so a previously-approved posting gets a fresh look
    if its content changed.

    Raises:
        JobNotFoundError: If job not found
        JobNotOwnedByCompanyError: If job is not owned by the company
        JobCannotBeUpdatedError: If job status doesn't allow updates
    """
    job = await get_by_id_or_raise(
        session,
        Job,
        job_id,
        lambda pk: JobNotFoundError(f"Job with ID {pk} not found"),
        options=[selectinload(Job.company)],  # pyright: ignore[reportArgumentType]
    )

    if job.company_id != company_id:
        raise JobNotOwnedByCompanyError(
            f"Job {job_id} is not owned by company {company_id}"
        )

    if job.status not in (JobStatus.PENDING_APPROVAL, JobStatus.PUBLISHED):
        raise JobCannotBeUpdatedError(
            f"Job {job_id} with status {job.status} cannot be updated"
        )

    if job_data.status is not None and job_data.status != job.status:
        raise JobCannotBeUpdatedError("Companies cannot change job status")

    if job_data.title is not None:
        job.title = job_data.title
    if job_data.short_description is not None:
        job.short_description = job_data.short_description
    if job_data.description is not None:
        job.description = job_data.description
    if job_data.requirements is not None:
        job.requirements = [r.model_dump() for r in job_data.requirements]
    if job_data.tags is not None:
        job.tags = list(job_data.tags)
    if job_data.location is not None:
        job.location = job_data.location
    if job_data.salary_min is not None:
        job.salary_min = job_data.salary_min
    if job_data.salary_max is not None:
        job.salary_max = job_data.salary_max

    job.updated_at = datetime.now(timezone.utc)
    await session.flush()

    company = job.company
    admin_emails = await get_all_admin_emails(session)
    if admin_emails:
        from src.core.infrastructure.config import settings

        admin_url = f"{settings.frontend_base_url}/login?redirect=/admin/jobs"
        _plain = f"פרסום משרה עודכן: {job.title} ({company.name})"
        _html = build_job_updated_html(
            job_title=job.title,
            company_name=company.name or "",
            location=job.location,
            job_id=job.id or 0,
            status=str(job.status),
            admin_url=admin_url,
        )
        defer_after_commit(
            lambda: enqueue_email_task(
                to=admin_emails,
                subject="פרסום משרה עודכן – RS Recruiting",
                body=_plain,
                html_body=_html,
            )
        )

    return JobRead.model_validate(job)


async def delete_job(job_id: int, company_id: int, session: AsyncSession) -> None:
    """Restricted to PENDING_APPROVAL: once a job is PUBLISHED it has been
    admin-reviewed and may already be visible to candidates, so removing it
    goes through the admin-driven close/reject flow instead of a company
    self-service delete.

    Raises:
        JobNotFoundError: If job not found
        JobNotOwnedByCompanyError: If job is not owned by the company
        JobCannotBeDeletedError: If job status doesn't allow deletion
    """
    job = await get_by_id_or_raise(
        session, Job, job_id, lambda pk: JobNotFoundError(f"Job with ID {pk} not found")
    )

    if job.company_id != company_id:
        raise JobNotOwnedByCompanyError(
            f"Job {job_id} is not owned by company {company_id}"
        )

    if job.status != JobStatus.PENDING_APPROVAL:
        raise JobCannotBeDeletedError(
            f"Job {job_id} with status {job.status} cannot be deleted. "
            "Only jobs with PENDING_APPROVAL status can be deleted."
        )

    await session.delete(job)
    await session.flush()
