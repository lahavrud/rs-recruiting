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
from src.core.matching import cosine_similarity_score
from src.core.tasks import enqueue_email_task
from src.enums import JobStatus
from src.models import Application, CandidateProfile, CompanyProfile, Job
from src.schemas import JobCreate, JobRead, JobUpdate
from src.schemas.companies import (
    CompanyApplicationCandidateRead,
    CompanyApplicationRead,
    CompanyJobRecommendationRead,
)
from src.services.admin.companies import get_all_admin_emails
from src.services.exceptions import (
    CompanyNotFoundError,
    JobCannotBeDeletedError,
    JobCannotBeUpdatedError,
    JobNotFoundError,
    JobNotOwnedByCompanyError,
)
from src.templates.email import build_job_updated_html, build_new_job_html


async def create_job(
    job_data: JobCreate, company_id: int, session: AsyncSession
) -> JobRead:
    """Always starts in PENDING_APPROVAL — companies cannot publish directly,
    so every posting goes through admin review first. Notifies all admins
    by email so the review queue doesn't rely on them polling the admin UI.

    Raises:
        CompanyNotFoundError: If company not found
    """
    # Verify company exists
    company = await get_by_id_or_raise(
        session,
        CompanyProfile,
        company_id,
        lambda pk: CompanyNotFoundError(f"Company with ID {pk} not found"),
    )

    # Create job with PENDING_APPROVAL status
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

    # Send email notification to all admins
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

    # Verify ownership
    if job.company_id != company_id:
        raise JobNotOwnedByCompanyError(
            f"Job {job_id} is not owned by company {company_id}"
        )

    # Verify job can be updated (only PENDING_APPROVAL or PUBLISHED)
    if job.status not in (JobStatus.PENDING_APPROVAL, JobStatus.PUBLISHED):
        raise JobCannotBeUpdatedError(
            f"Job {job_id} with status {job.status} cannot be updated"
        )

    # Companies cannot change status (only admin can)
    if job_data.status is not None and job_data.status != job.status:
        raise JobCannotBeUpdatedError("Companies cannot change job status")

    # Update fields
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

    # Update updated_at timestamp
    job.updated_at = datetime.now(timezone.utc)
    await session.flush()

    # Send email notification to all admins
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

    # Verify ownership
    if job.company_id != company_id:
        raise JobNotOwnedByCompanyError(
            f"Job {job_id} is not owned by company {company_id}"
        )

    # Verify job can be deleted (only PENDING_APPROVAL)
    if job.status != JobStatus.PENDING_APPROVAL:
        raise JobCannotBeDeletedError(
            f"Job {job_id} with status {job.status} cannot be deleted. "
            "Only jobs with PENDING_APPROVAL status can be deleted."
        )

    # Delete the job
    await session.delete(job)
    await session.flush()


async def list_job_applications(
    job_id: int,
    company_id: int,
    session: AsyncSession,
) -> list[CompanyApplicationRead]:
    """Return all applications for a job owned by the given company.

    Raises:
        JobNotFoundError: If job not found
        JobNotOwnedByCompanyError: If job is not owned by the company
    """
    job = await get_by_id_or_raise(
        session, Job, job_id, lambda pk: JobNotFoundError(f"Job with ID {pk} not found")
    )
    if job.company_id != company_id:
        raise JobNotOwnedByCompanyError(
            f"Job {job_id} is not owned by company {company_id}"
        )

    result = await session.execute(
        select(Application, CandidateProfile)
        .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)  # pyright: ignore[reportArgumentType]
        .where(Application.job_id == job_id)  # pyright: ignore[reportArgumentType]
        .order_by(Application.created_at.desc())  # pyright: ignore[reportArgumentType]
    )
    rows = result.all()
    return [
        CompanyApplicationRead(
            id=app.id or 0,
            job_id=app.job_id,
            candidate_id=app.candidate_id,
            status=str(app.status),
            created_at=app.created_at,
            updated_at=app.updated_at,
            candidate=CompanyApplicationCandidateRead(
                id=candidate.id or 0,
                full_name=candidate.full_name,
                email=candidate.email,
                phone=candidate.phone,
            ),
        )
        for app, candidate in rows
    ]


_RECOMMENDATION_POOL = 50
_RECOMMENDATION_LIMIT = 10
_RECOMMENDATION_MIN_SCORE = 0.50


async def get_job_recommendations(
    job_id: int,
    company_id: int,
    session: AsyncSession,
) -> list[CompanyJobRecommendationRead]:
    """Return AI-ranked candidate recommendations for a published company job.

    Finds candidates with embeddings who have NOT already applied, ranked by
    cosine similarity to the job's embedding. Returns an empty list when the
    job has no embedding yet (not yet published or not yet indexed).

    Raises:
        JobNotFoundError: If job not found
        JobNotOwnedByCompanyError: If job is not owned by the company
    """
    job = await get_by_id_or_raise(
        session, Job, job_id, lambda pk: JobNotFoundError(f"Job with ID {pk} not found")
    )
    if job.company_id != company_id:
        raise JobNotOwnedByCompanyError(
            f"Job {job_id} is not owned by company {company_id}"
        )
    if job.embedding is None:
        return []

    applied_candidate_ids: set[int] = {
        row[0]
        for row in (
            await session.execute(
                select(Application.candidate_id).where(Application.job_id == job_id)  # pyright: ignore[reportArgumentType]
            )
        ).all()
    }

    distance = CandidateProfile.embedding.cosine_distance(job.embedding)
    rows = (
        await session.execute(
            select(CandidateProfile, distance.label("dist"))
            .where(
                CandidateProfile.embedding.is_not(None),  # pyright: ignore[reportArgumentType]
                ~CandidateProfile.id.in_(applied_candidate_ids),  # pyright: ignore[reportArgumentType]
            )
            .order_by(distance)
            .limit(_RECOMMENDATION_POOL)
        )
    ).all()

    results: list[CompanyJobRecommendationRead] = []
    for candidate, dist in rows:
        score = cosine_similarity_score(dist)
        if score < _RECOMMENDATION_MIN_SCORE:
            break
        results.append(
            CompanyJobRecommendationRead(
                candidate_id=candidate.id or 0,
                full_name=candidate.full_name,
                email=candidate.email,
                phone=candidate.phone,
                score=score,
            )
        )
        if len(results) >= _RECOMMENDATION_LIMIT:
            break
    return results
