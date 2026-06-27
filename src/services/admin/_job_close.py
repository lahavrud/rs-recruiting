"""Job-closing cascade logic for admin service.

Split out of jobs.py to satisfy the 300-line file cap.
Exercised end-to-end via tests/services/admin/test_jobs.py.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.transactions import defer_after_commit
from src.core.tasks import enqueue_email_task
from src.enums import ApplicationStatus
from src.models import Application, CandidateProfile
from src.services.utils.audit import record_audit_event
from src.templates.email import build_job_closed_candidate_html

_ACTIVE_STATUSES = (ApplicationStatus.NEW, ApplicationStatus.APPROVED_BY_ADMIN)


async def close_active_applications(
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
