"""Email notifications for admin-initiated job changes."""

from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.tasks import queue_email
from rs_shared.models import Job
from rs_shared.templates.email import (
    build_job_admin_edited_html,
    build_job_closed_company_html,
)

FIELD_LABELS: dict[str, str] = {
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


async def _dispatch_email(
    session: AsyncSession, email: str, subject: str, body: str, html_body: str
) -> None:
    await queue_email(
        session, to=email, subject=subject, body=body, html_body=html_body
    )


async def notify_company_of_update(
    session: AsyncSession,
    job: Job,
    *,
    old_title: str,
    title_changed: bool,
    changed_labels: list[str],
    is_closing: bool,
) -> None:
    """Queue the company's notification for an admin job edit.

    Must still run before any session.refresh() of the Job — refresh re-fetches
    the row and expires selectinloaded relationships, making company/user
    inaccessible via async lazy-load afterward.
    """
    if job.company.user is None:
        return

    email = job.company.user.email
    new_title = job.title
    company_name = job.company.name
    dashboard_url = f"{settings.frontend_base_url}/login?redirect=/company/jobs"

    if is_closing:
        await _dispatch_email(
            session,
            email,
            *_build_job_closure_email(
                new_title=new_title,
                company_name=company_name,
                dashboard_url=dashboard_url,
            ),
        )

    status_label = FIELD_LABELS.get("status")
    notify_labels = [
        lbl for lbl in changed_labels if not (is_closing and lbl == status_label)
    ]
    if notify_labels:
        await _dispatch_email(
            session,
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
