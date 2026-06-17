"""Admin service layer for direct job CRUD.

Separate from `jobs_admin.py` (approval workflow) — these functions let
an admin manage any job in any status, including creating jobs directly
on behalf of a company that hasn't been onboarded yet.
"""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.config import settings
from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.core.infrastructure.transactions import defer_after_commit
from src.core.tasks import enqueue_email_task
from src.enums import ApplicationStatus, JobStatus
from src.models import Application, CandidateProfile, CompanyProfile, Job
from src.schemas import JobAdminCreate, JobAdminUpdate, JobRead
from src.services.exceptions import CompanyNotFoundError, JobNotFoundError
from src.services.utils.audit import record_audit_event
from src.templates.email import (
    build_job_admin_edited_html,
    build_job_closed_candidate_html,
    build_job_closed_company_html,
)

_FIELD_LABELS: dict[str, str] = {
    "title": "כותרת",
    "short_description": "תיאור קצר",
    "description": "תיאור מפורט",
    "requirements": "דרישות",
    "tags": "תגיות",
    "is_featured": "מוצגת",
    "location": "מיקום",
    "salary_min": "שכר מינימום",
    "salary_max": "שכר מקסימום",
    "status": "סטטוס",
}


async def list_jobs(
    session: AsyncSession,
    *,
    status: JobStatus | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[JobRead]:
    """One page of jobs across all statuses, newest first.

    `status` filters to a single status when provided (None returns all).
    """
    page_size = clamp_limit(limit)
    base = select(Job)
    if status is not None:
        base = base.where(Job.status == status)  # pyright: ignore[reportArgumentType]
    query = apply_cursor(
        base,
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


async def admin_create_job(data: JobAdminCreate, session: AsyncSession) -> JobRead:
    """Create a job directly under an existing company profile.

    Raises:
        CompanyNotFoundError: If the referenced `company_id` does not exist.
    """
    await get_by_id_or_raise(
        session,
        CompanyProfile,
        data.company_id,
        lambda pk: CompanyNotFoundError(f"Company profile {pk} not found"),
    )

    job = Job(
        company_id=data.company_id,
        title=data.title,
        short_description=data.short_description,
        description=data.description,
        requirements=[r.model_dump() for r in data.requirements],
        tags=list(data.tags),
        is_featured=data.is_featured,
        location=data.location,
        salary_min=data.salary_min,
        salary_max=data.salary_max,
        status=data.status,
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return JobRead.model_validate(job)


def _build_job_closure_email(
    *, new_title: str, company_name: str, dashboard_url: str
) -> tuple[str, str, str]:
    subject = f"משרה נסגרה על-ידי המנהל — {new_title} — RS Recruiting"
    body = (
        f"שלום {company_name},\n\n"
        f"מנהל המערכת סגר את המשרה '{new_title}'.\n"
        "המשרה הוסרה מלוח המשרות הציבורי, "
        "והמועמדים הפעילים קיבלו הודעה.\n\n"
        f"לפרטים נוספים: {dashboard_url}\n\nצוות RS Recruiting"
    )
    html_body = build_job_closed_company_html(
        job_title=new_title,
        company_name=company_name,
        dashboard_url=dashboard_url,
    )
    return subject, body, html_body


def _build_job_update_email(
    *,
    new_title: str,
    old_title: str,
    title_changed: bool,
    company_name: str,
    dashboard_url: str,
    notify_labels: list[str],
) -> tuple[str, str, str]:
    former_title = old_title if title_changed else None
    subject = "פרסום משרה עודכן על-ידי המנהל — RS Recruiting"
    body = (
        f"פרסום המשרה '{new_title}'"
        + (f" ({old_title} לשעבר)" if title_changed else "")
        + f" עודכן על-ידי המנהל. שדות שעודכנו: {', '.join(notify_labels)}"
    )
    html_body = build_job_admin_edited_html(
        job_title=new_title,
        company_name=company_name,
        changed_fields=notify_labels,
        dashboard_url=dashboard_url,
        former_title=former_title,
    )
    return subject, body, html_body


def _dispatch_email(email: str, subject: str, body: str, html_body: str) -> None:
    defer_after_commit(
        lambda: enqueue_email_task(
            to=email, subject=subject, body=body, html_body=html_body
        )
    )


def _notify_company_of_update(
    job: Job,
    *,
    old_title: str,
    title_changed: bool,
    changed_labels: list[str],
    is_closing: bool,
) -> None:
    """Capture notification data before session.refresh() — refresh re-fetches
    the Job row and expires selectinloaded relationships, making company/user
    inaccessible via async lazy-load afterward.
    """
    if job.company.user is None:
        return

    email = job.company.user.email
    new_title = job.title
    company_name = job.company.name
    dashboard_url = f"{settings.frontend_base_url}/login?redirect=/company/jobs"

    if is_closing:
        _dispatch_email(
            email,
            *_build_job_closure_email(
                new_title=new_title,
                company_name=company_name,
                dashboard_url=dashboard_url,
            ),
        )

    status_label = _FIELD_LABELS.get("status")
    notify_labels = [
        lbl for lbl in changed_labels if not (is_closing and lbl == status_label)
    ]
    if notify_labels:
        _dispatch_email(
            email,
            *_build_job_update_email(
                new_title=new_title,
                old_title=old_title,
                title_changed=title_changed,
                company_name=company_name,
                dashboard_url=dashboard_url,
                notify_labels=notify_labels,
            ),
        )


async def update_job(
    job_id: int,
    data: JobAdminUpdate,
    session: AsyncSession,
    *,
    actor_user_id: int | None = None,
) -> JobRead:
    """Apply a partial update to a job. Admin can edit any field at any status.

    Notifies the company by email when at least one field changes and the
    company has an attached user account. Admin-created orphan companies
    (no user) are silently skipped.

    Raises:
        JobNotFoundError: If no job with that id exists.
    """
    result = await session.execute(
        select(Job)
        .options(selectinload(Job.company).selectinload(CompanyProfile.user))
        .where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundError(f"Job {job_id} not found")

    # model_dump serializes nested pydantic items (e.g. JobRequirementItem)
    # to plain dicts, which is exactly what the JSONB column wants.
    payload = data.model_dump(exclude_unset=True)

    changed_labels = [
        _FIELD_LABELS.get(field, field)
        for field, value in payload.items()
        if getattr(job, field) != value
    ]
    old_title = job.title
    old_status = job.status
    title_changed = "title" in payload and payload["title"] != old_title

    for field, value in payload.items():
        setattr(job, field, value)
    job.updated_at = datetime.now(timezone.utc)

    await session.flush()

    is_closing = old_status == JobStatus.PUBLISHED and job.status == JobStatus.CLOSED

    _notify_company_of_update(
        job,
        old_title=old_title,
        title_changed=title_changed,
        changed_labels=changed_labels,
        is_closing=is_closing,
    )

    # When a published job is closed, notify all active applicants and
    # transition their applications to JOB_CLOSED.
    if is_closing:
        await _close_active_applications(
            job_id, job.title, session, actor_user_id=actor_user_id
        )

    await session.refresh(job)
    return JobRead.model_validate(job)


_ACTIVE_STATUSES = (ApplicationStatus.NEW, ApplicationStatus.APPROVED_BY_ADMIN)


async def _close_active_applications(
    job_id: int,
    job_title: str,
    session: AsyncSession,
    *,
    actor_user_id: int | None = None,
) -> None:
    """Transition active applications to JOB_CLOSED and send closure emails."""
    apps_result = await session.execute(
        select(Application)
        .options(selectinload(Application.candidate))  # pyright: ignore[reportArgumentType]
        .where(
            Application.job_id == job_id,  # pyright: ignore[reportArgumentType]
            Application.status.in_(_ACTIVE_STATUSES),  # pyright: ignore[reportArgumentType]
        )
    )
    apps = list(apps_result.scalars().all())

    now = datetime.now(timezone.utc)
    for app in apps:
        app.status = ApplicationStatus.JOB_CLOSED
        app.updated_at = now

    await session.flush()

    for app in apps:
        await record_audit_event(
            session,
            actor_user_id=actor_user_id,
            action="application.status_change",
            target_type="Application",
            target_id=app.id,
            detail=f"JOB_CLOSED (cascade, job {job_id})",
        )

    for app in apps:
        candidate: CandidateProfile = app.candidate
        _to = candidate.email
        _name = candidate.full_name
        _title = job_title
        defer_after_commit(
            lambda to=_to, name=_name, title=_title: enqueue_email_task(
                to=to,
                subject=f"עדכון בנוגע למועמדותך למשרת {title} — RS Recruiting",
                body=(
                    f"{name} שלום,\n\n"
                    f"תודה על מועמדותך ועל העניין שגילית בתפקיד {title}.\n\n"
                    "לצערנו, המשרה נסגרה. הדבר אינו קשור לפרופיל שלך אלא נובע "
                    "מנסיבות פנימיות — כגון איוש המשרה או שינוי בצרכי הגיוס.\n\n"
                    "נשמח לשמור את קורות החיים שלך ולפנות אליך כשתעמוד על הפרק "
                    "משרה שתתאים לכישוריך.\n\n"
                    "בברכה,\nצוות RS Recruiting"
                ),
                html_body=build_job_closed_candidate_html(
                    candidate_name=name,
                    job_title=title,
                ),
            )
        )


async def delete_job(job_id: int, session: AsyncSession) -> None:
    """Hard-delete a job and cascade through its applications.

    Candidate profiles and resume files are preserved — they belong to the
    candidate, not the job.

    Raises:
        JobNotFoundError: If no job with that id exists.
    """
    job = await get_by_id_or_raise(
        session, Job, job_id, lambda pk: JobNotFoundError(f"Job {pk} not found")
    )

    await session.execute(
        delete(Application).where(Application.job_id == job_id)  # pyright: ignore[reportArgumentType]
    )
    await session.delete(job)
    await session.flush()
