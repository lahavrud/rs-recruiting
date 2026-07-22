"""Job-closing cascade logic for admin service.

Split out of jobs.py to satisfy the 300-line file cap.
Exercised end-to-end via tests/services/admin/test_jobs.py.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from rs_shared.core.infrastructure.transactions import defer_after_commit
from rs_shared.core.tasks import enqueue_email_task
from rs_shared.enums import ACTIVE_APPLICATION_STATUSES, ApplicationStatus
from rs_shared.models import Application, CandidateProfile
from rs_shared.services.utils.audit import record_audit_event
from rs_shared.templates.email import build_job_closed_candidate_html

# In-flight applications are the ones swept into JOB_CLOSED when the parent job
# closes — see ``ACTIVE_APPLICATION_STATUSES`` in enums.py.


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
            Application.status.in_(ACTIVE_APPLICATION_STATUSES),  # pyright: ignore[reportArgumentType]
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
        # Tombstoned candidates keep their Application rows (account deletion
        # preserves recruiting history and never moves the status), so they
        # reach the sweep above and are audited like anyone else. They must not
        # reach the mail: ``scrub_candidate_pii`` rewrites the address to the
        # non-routable ``deleted-{id}@deleted``, so every send is a guaranteed
        # hard bounce against the shared sender reputation — and the person
        # asked to stop hearing from us.
        if candidate.deleted_at is not None:
            continue
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
