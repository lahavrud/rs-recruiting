"""Job-closing cascade logic for admin service.

Split out of jobs.py to satisfy the 300-line file cap.
Exercised end-to-end via tests/services/admin/test_jobs.py.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from rs_shared.core.tasks import queue_email
from rs_shared.enums import ACTIVE_APPLICATION_STATUSES, ApplicationStatus
from rs_shared.models import Application, CandidateProfile
from rs_shared.services.utils.audit import record_audit_event
from rs_shared.templates.email import build_job_closed_candidate_html


async def close_active_applications(
    job_id: int,
    job_title: str,
    session: AsyncSession,
    *,
    actor_user_id: int | None = None,
) -> None:
    """Transition active applications to JOB_CLOSED and send closure emails.

    "Active" means still in flight — pre-decision, so the closing job is the
    thing that ends them. Terminal applications are left alone: their outcome
    already happened and is not the job's to overwrite. The set is
    ``ACTIVE_APPLICATION_STATUSES``, derived from ``ApplicationStatus.is_active``
    so it cannot drift from the enum.
    """
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
        name = candidate.full_name
        # One row per application, so a re-close never re-emails a candidate
        # who was already notified.
        await queue_email(
            session,
            to=candidate.email,
            subject=f"עדכון בנוגע למועמדותך למשרת {job_title} — RS Recruiting",
            body=(
                f"{name} שלום,\n\n"
                f"תודה על מועמדותך ועל העניין שגילית בתפקיד {job_title}.\n\n"
                "לצערנו, המשרה נסגרה. הדבר אינו קשור לפרופיל שלך אלא נובע "
                "מנסיבות פנימיות — כגון איוש המשרה או שינוי בצרכי הגיוס.\n\n"
                "נשמח לשמור את קורות החיים שלך ולפנות אליך כשתעמוד על הפרק "
                "משרה שתתאים לכישוריך.\n\n"
                "בברכה,\nצוות RS Recruiting"
            ),
            html_body=build_job_closed_candidate_html(
                candidate_name=name,
                job_title=job_title,
            ),
            dedup_key=f"job_closed:{app.id}",
        )
