"""Daily admin digest of new applications (#1159).

Replaces the one-email-per-application admin notification. Run once a day by
``send_admin_digest_task`` (EventBridge Scheduler, 08:00 Asia/Jerusalem).

There is no digest table: the ``email_outbox`` row *is* the record.

- **Idempotency.** The row's ``dedup_key`` is ``admin_application_digest:<Israel
  date>``, and ``dedup_key`` is UNIQUE, so an SQS redelivery (or a manual
  re-run) on the same day queues nothing.
- **Window.** From the ``created_at`` of the latest digest row to now. A day
  with no applications writes no row, so the next digest simply picks up from
  the last one that was sent, and a missed scheduler tick catches up in one
  email. No previous digest → the last 24h. Capped at 7 days either way.

Trade-off: the window advances when the row is *queued*. If that row later ends
up FAILED, its applications are not re-sent in the next digest. The outbox's
own retries and sweeper cover transient failures; the in-app notification
center (#1164) is the planned backstop.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.tasks import queue_email
from rs_shared.enums import ApplicationStatus
from rs_shared.models import (
    Application,
    CandidateProfile,
    CompanyProfile,
    EmailOutbox,
    Job,
)
from rs_shared.services.admin._filters import candidate_not_deleted
from rs_shared.services.utils.recipients import get_admin_notification_recipients
from rs_shared.templates.email import build_admin_application_digest_html

logger = logging.getLogger(__name__)

DIGEST_KEY_PREFIX = "admin_application_digest:"
DIGEST_TZ = ZoneInfo("Asia/Jerusalem")
FIRST_DIGEST_WINDOW = timedelta(hours=24)
MAX_LOOKBACK = timedelta(days=7)
NAMES_PER_JOB = 10
# Busiest jobs listed in full; the rest collapse into one summary line so a
# busy day doesn't produce a wall of names. The total still counts them all.
JOBS_LIMIT = 5

# Mirrors frontend/src/locales/he/admin.json → applications.statusLabels.
STATUS_LABELS: dict[ApplicationStatus, str] = {
    ApplicationStatus.PENDING_ADMIN_REVIEW: "ממתין לבדיקה",
    ApplicationStatus.APPROVED_BY_ADMIN: "אושר",
    ApplicationStatus.INTERVIEWING: "בראיונות",
    ApplicationStatus.OFFER: "הצעה",
    ApplicationStatus.REJECTED_BY_COMPANY: "נדחה ע״י החברה",
    ApplicationStatus.REJECTED_BY_ADMIN: "נדחה",
    ApplicationStatus.HIRED: "גויס",
    ApplicationStatus.JOB_CLOSED: "משרה נסגרה",
    ApplicationStatus.WITHDRAWN: "בוטלה מועמדות",
}


async def send_application_digest(
    session: AsyncSession, *, now: datetime | None = None
) -> int:
    """Queue today's digest. Returns the number of applications it covers.

    Returns 0, and queues nothing, when there are no new applications, no
    recipients, or today's digest was already queued. Must run inside a
    ``transactional()`` block (``queue_email`` writes an outbox row).
    """
    now = now or datetime.now(timezone.utc)
    start = await _window_start(session, now)
    rows = await _applications_between(session, start, now)
    if not rows:
        logger.info("admin_digest_empty", extra={"window_start": start.isoformat()})
        return 0

    recipients = await get_admin_notification_recipients(session)
    if not recipients:
        logger.warning("admin_digest_no_recipients", extra={"applications": len(rows)})
        return 0

    all_jobs = _group_by_job(rows)
    jobs, others = all_jobs[:JOBS_LIMIT], _others_phrase(all_jobs[JOBS_LIMIT:])
    total = len(rows)
    admin_url = f"{settings.frontend_base_url}/login?redirect=/admin/applications"
    day = now.astimezone(DIGEST_TZ).date().isoformat()

    outbox_id = await queue_email(
        session,
        to=recipients,
        subject=f"סיכום מועמדויות יומי — {_count_phrase(total)}",
        body=_plain_text(jobs, others, total, admin_url),
        html_body=build_admin_application_digest_html(
            total=total, jobs=jobs, others=others, admin_url=admin_url
        ),
        dedup_key=f"{DIGEST_KEY_PREFIX}{day}",
    )
    if outbox_id is None:
        logger.info("admin_digest_already_sent", extra={"day": day})
        return 0

    logger.info(
        "admin_digest_sent",
        extra={"applications": total, "jobs": len(all_jobs), "outbox_id": outbox_id},
    )
    return total


async def _window_start(session: AsyncSession, now: datetime) -> datetime:
    last_sent = (
        await session.execute(
            select(func.max(EmailOutbox.created_at)).where(
                EmailOutbox.dedup_key.like(f"{DIGEST_KEY_PREFIX}%")  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
            )
        )
    ).scalar_one_or_none()
    start = last_sent or (now - FIRST_DIGEST_WINDOW)
    return max(start, now - MAX_LOOKBACK)


async def _applications_between(
    session: AsyncSession, start: datetime, end: datetime
) -> list:
    result = await session.execute(
        select(
            Job.id,
            Job.title,
            CompanyProfile.name,
            CandidateProfile.full_name,
            Application.status,
        )
        .join(Job, Application.job_id == Job.id)  # pyright: ignore[reportArgumentType]
        .join(CompanyProfile, Job.company_id == CompanyProfile.id)  # pyright: ignore[reportArgumentType]
        .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)  # pyright: ignore[reportArgumentType]
        .where(
            Application.created_at > start,  # pyright: ignore[reportArgumentType]
            Application.created_at <= end,  # pyright: ignore[reportArgumentType]
            candidate_not_deleted(),
        )
        .order_by(Application.created_at)  # pyright: ignore[reportArgumentType]
    )
    return list(result.all())


def _group_by_job(rows: list) -> list[dict]:
    """Busiest job first; each lists up to NAMES_PER_JOB applicants, oldest first."""
    groups: dict[int, dict] = {}
    for job_id, title, company_name, candidate_name, status in rows:
        group = groups.setdefault(
            job_id,
            {"title": title, "company_name": company_name or "", "names": []},
        )
        group["names"].append(
            {"name": candidate_name, "status_label": STATUS_LABELS.get(status, "")}
        )

    jobs = []
    for group in groups.values():
        names = group.pop("names")
        jobs.append(
            {
                **group,
                "count": len(names),
                "applicants": names[:NAMES_PER_JOB],
                "more": max(len(names) - NAMES_PER_JOB, 0),
            }
        )
    jobs.sort(key=lambda j: (-j["count"], j["title"]))
    return jobs


def _count_phrase(total: int) -> str:
    return "מועמדות חדשה אחת" if total == 1 else f"{total} מועמדויות חדשות"


def _others_phrase(rest: list[dict]) -> str | None:
    """Summary line for jobs past JOBS_LIMIT, e.g. "ועוד 2 משרות עם 3 מועמדויות"."""
    if not rest:
        return None
    jobs = "משרה אחת" if len(rest) == 1 else f"{len(rest)} משרות"
    count = sum(j["count"] for j in rest)
    applications = "מועמדות אחת" if count == 1 else f"{count} מועמדויות"
    return f"ועוד {jobs} עם {applications}"


def _plain_text(
    jobs: list[dict], others: str | None, total: int, admin_url: str
) -> str:
    lines = [f"סיכום מועמדויות יומי — {_count_phrase(total)}", ""]
    for job in jobs:
        lines.append(f"{job['title']} ({job['company_name']}) — {job['count']}")
        lines.extend(
            f"  • {a['name']} — {a['status_label']}" for a in job["applicants"]
        )
        if job["more"]:
            lines.append(f"  ועוד {job['more']}")
        lines.append("")
    if others:
        lines.extend([others, ""])
    lines.append(f"מעבר לניהול: {admin_url}")
    return "\n".join(lines)
