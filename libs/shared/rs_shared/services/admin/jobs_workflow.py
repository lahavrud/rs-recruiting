"""Admin job approval service functions."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from rs_shared.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from rs_shared.core.infrastructure.transactions import defer_after_commit
from rs_shared.core.tasks import enqueue_embed_job_task, queue_email
from rs_shared.enums import JobStatus
from rs_shared.models import CompanyProfile, Job
from rs_shared.schemas import JobRead
from rs_shared.services.exceptions import JobNotFoundError, JobNotPendingError
from rs_shared.services.utils.audit import record_audit_event
from rs_shared.templates.email import build_job_contact_html


async def _load_job_with_company_and_user(session: AsyncSession, job_id: int) -> Job:
    """Fetch a Job with its CompanyProfile + owning User eager-loaded.

    Single round-trip via two `selectinload` follow-ups instead of three
    sequential SELECTs in the approve/reject/contact flows.
    """
    result = await session.execute(
        select(Job)
        .options(selectinload(Job.company).selectinload(CompanyProfile.user))
        .where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundError(f"Job with ID {job_id} not found")
    return job


async def list_pending_jobs(
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[JobRead]:
    """One page of pending-approval jobs, newest first."""
    page_size = clamp_limit(limit)
    query = apply_cursor(
        select(Job)
        .options(selectinload(Job.company))
        .where(Job.status == JobStatus.PENDING_APPROVAL),  # pyright: ignore[reportArgumentType]
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


async def approve_job(
    job_id: int, session: AsyncSession, *, actor_user_id: int | None = None
) -> JobRead:
    """Approve a job posting by changing status to PUBLISHED.

    Sets Job.status=PUBLISHED and sends email notification to the company.

    Args:
        job_id: ID of the job to approve
        session: Database session

    Returns:
        Approved job as JobRead schema

    Raises:
        JobNotFoundError: If job not found
        JobNotPendingError: If job is not pending approval
    """
    job = await _load_job_with_company_and_user(session, job_id)

    # Validate it's pending
    if job.status != JobStatus.PENDING_APPROVAL:
        raise JobNotPendingError(
            f"Job {job_id} is not pending approval (current status: {job.status})"
        )

    # Approve the job
    job.status = JobStatus.PUBLISHED
    job.updated_at = datetime.now(timezone.utc)
    await session.flush()

    # Now that it's published it becomes matchable — embed it (after commit) so
    # subsequent candidate matches can rank against it.
    published_job_id = job.id
    defer_after_commit(lambda: enqueue_embed_job_task(published_job_id))

    await record_audit_event(
        session,
        actor_user_id=actor_user_id,
        action="job_approved",
        target_type="job",
        target_id=job.id,
        detail=job.title,
    )

    # Emails only go out when the company has an active user account.
    # Admin-created (orphan) profiles have no inbox to deliver to, so we
    # skip the send — the contact_email captured on the profile is for
    # reference only until a user is attached.
    if job.company.user is None:
        return JobRead.model_validate(job)

    await queue_email(
        session,
        to=job.company.user.email,
        subject="Job Posting Approved",
        body=(
            f"Your job posting '{job.title}' has been approved "
            f"and is now published on the job board.\n\n"
            f"Job Title: {job.title}\n"
            f"Location: {job.location}\n"
            f"Job ID: {job.id}\n\n"
            "Candidates can now view and apply for this position."
        ),
    )

    return JobRead.model_validate(job)


async def reject_job(
    job_id: int, session: AsyncSession, *, actor_user_id: int | None = None
) -> None:
    """Reject a job posting by changing status to CLOSED.

    Sets Job.status=CLOSED and sends email notification to the company.

    Args:
        job_id: ID of the job to reject
        session: Database session

    Raises:
        JobNotFoundError: If job not found
        JobNotPendingError: If job is not pending approval
    """
    job = await _load_job_with_company_and_user(session, job_id)

    # Validate it's pending
    if job.status != JobStatus.PENDING_APPROVAL:
        raise JobNotPendingError(
            f"Job {job_id} is not pending approval (current status: {job.status})"
        )

    # See approve_job — skip the email send when there's no attached user.
    job_title = job.title
    job_location = job.location

    job.status = JobStatus.CLOSED
    job.updated_at = datetime.now(timezone.utc)
    await session.flush()

    await record_audit_event(
        session,
        actor_user_id=actor_user_id,
        action="job_rejected",
        target_type="job",
        target_id=job.id,
        detail=job_title,
    )

    if job.company.user is None:
        return

    await queue_email(
        session,
        to=job.company.user.email,
        subject="Job Posting Rejected",
        body=(
            f"Your job posting '{job_title}' has been rejected "
            f"and will not be published.\n\n"
            f"Job Title: {job_title}\n"
            f"Location: {job_location}\n"
            f"Job ID: {job_id}\n\n"
            "If you believe this is an error, please contact support "
            "or update the job posting and resubmit for approval."
        ),
    )


async def contact_job(job_id: int, admin_note: str, session: AsyncSession) -> None:
    """Send a contextual email from admin to the company owning a job posting.

    The job may be in any status — this is a pre-decision communication tool.

    Args:
        job_id: ID of the job being discussed
        admin_note: Optional message body from the admin
        session: Database session

    Raises:
        JobNotFoundError: If job not found
    """
    job = await _load_job_with_company_and_user(session, job_id)

    if job.company.user is None:
        return
    await queue_email(
        session,
        to=job.company.user.email,
        subject="פנייה בנוגע למשרה — RS Recruiting",
        body=(
            f"פנייה ממנהל המערכת בנוגע למשרת '{job.title}'.\n\n"
            f"{admin_note}\n\n"
            "לשאלות ופניות נוספות, אנא צרו קשר עם צוות RS Recruiting."
        ),
        html_body=build_job_contact_html(
            job_title=job.title,
            company_name=job.company.name,
            admin_note=admin_note,
        ),
    )
