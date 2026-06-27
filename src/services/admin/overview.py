"""Admin overview aggregation — real counts replacing capped page-length heuristics."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import ApplicationStatus, InviteTokenStatus, JobStatus, UserRole
from src.models import (
    Application,
    CandidateProfile,
    CompanyProfile,
    InviteToken,
    Job,
    User,
)

TOP_JOBS_LIMIT = 5
RECENT_ITEMS_PER_TYPE = 2


async def get_overview(session: AsyncSession) -> dict:
    """Compute all admin dashboard counts sequentially on the shared session.

    asyncio.gather() with a shared AsyncSession is not safe — SQLAlchemy's
    session is not designed for concurrent coroutine access and deadlocks
    against its own internal connection mutex.
    """
    pending_invites = await _count_pending_invites(session)
    pending_companies = await _count_pending_companies(session)
    pending_jobs = await _count_pending_jobs(session)
    new_applications = await _count_new_applications(session)
    active_companies = await _count_active_companies(session)
    published_jobs = await _count_published_jobs(session)
    total_candidates = await _count_candidates(session)
    status_counts = await _count_application_statuses(session)
    top_jobs = await _top_jobs_by_applications(session)
    oldest_company_days = await _oldest_pending_company_days(session)
    oldest_job_days = await _oldest_pending_job_days(session)
    oldest_application_days = await _oldest_new_application_days(session)
    new_candidates_7d = await _new_candidates_7d(session)
    new_applications_7d = await _new_applications_7d(session)
    recent_companies = await _recent_pending_companies(session)
    recent_jobs = await _recent_pending_jobs(session)
    recent_applications = await _recent_new_applications(session)
    trend_30d = await _application_trend_30d(session)

    all_recent = recent_companies + recent_jobs + recent_applications
    all_recent.sort(key=lambda x: x["created_at"], reverse=True)

    return {
        "inbox": {
            "pending_invites": pending_invites,
            "pending_companies": pending_companies,
            "pending_jobs": pending_jobs,
            "new_applications": new_applications,
            "oldest_pending_company_days": oldest_company_days,
            "oldest_pending_job_days": oldest_job_days,
            "oldest_new_application_days": oldest_application_days,
        },
        "stats": {
            "active_companies": active_companies,
            "published_jobs": published_jobs,
            "total_candidates": total_candidates,
            "application_status_counts": status_counts,
            "top_jobs": top_jobs,
        },
        "pulse": {
            "new_candidates_7d": new_candidates_7d,
            "new_applications_7d": new_applications_7d,
            "recent_items": all_recent[:6],
            "trend_30d": trend_30d,
        },
    }


def _age_days(ts: datetime | None) -> int | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).days


async def _count_pending_invites(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(InviteToken)
        .where(
            InviteToken.status == InviteTokenStatus.PENDING  # pyright: ignore[reportArgumentType]
        )
    )
    return result.scalar_one()


async def _count_pending_companies(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(User)
        .join(CompanyProfile, User.id == CompanyProfile.user_id)  # pyright: ignore[reportArgumentType]
        .where(User.role == UserRole.COMPANY, User.is_active == False)  # noqa: E712
    )
    return result.scalar_one()


async def _count_pending_jobs(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Job)
        .where(
            Job.status == JobStatus.PENDING_APPROVAL  # pyright: ignore[reportArgumentType]
        )
    )
    return result.scalar_one()


async def _count_new_applications(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Application)
        .where(
            Application.status == ApplicationStatus.NEW  # pyright: ignore[reportArgumentType]
        )
    )
    return result.scalar_one()


async def _count_active_companies(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(CompanyProfile)
        .outerjoin(User, CompanyProfile.user_id == User.id)  # pyright: ignore[reportArgumentType]
        .where(
            (CompanyProfile.user_id == None)  # noqa: E711
            | (  # pyright: ignore[reportOperatorIssue]
                (User.role == UserRole.COMPANY) & (User.is_active == True)  # noqa: E712
            )
        )
    )
    return result.scalar_one()


async def _count_published_jobs(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Job)
        .where(
            Job.status == JobStatus.PUBLISHED  # pyright: ignore[reportArgumentType]
        )
    )
    return result.scalar_one()


async def _count_candidates(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(CandidateProfile))
    return result.scalar_one()


async def _count_application_statuses(session: AsyncSession) -> dict[str, int]:
    rows = (
        await session.execute(
            select(Application.status, func.count().label("n")).group_by(
                Application.status
            )  # pyright: ignore[reportArgumentType]
        )
    ).all()
    return {str(row[0]): row[1] for row in rows}


async def _top_jobs_by_applications(
    session: AsyncSession,
) -> list[dict]:
    app_count = func.count(Application.id).label("application_count")
    rows = (
        await session.execute(
            select(Job.id, Job.title, app_count)
            .join(Application, Application.job_id == Job.id)  # pyright: ignore[reportArgumentType]
            .group_by(Job.id, Job.title)  # pyright: ignore[reportArgumentType]
            .order_by(func.count(Application.id).desc())
            .limit(TOP_JOBS_LIMIT)
        )
    ).all()
    return [
        {"id": row[0], "title": row[1], "application_count": row[2]} for row in rows
    ]


async def _oldest_pending_company_days(session: AsyncSession) -> int | None:
    result = await session.execute(
        select(func.min(CompanyProfile.created_at))
        .join(User, User.id == CompanyProfile.user_id)  # pyright: ignore[reportArgumentType]
        .where(User.role == UserRole.COMPANY, User.is_active == False)  # noqa: E712
    )
    return _age_days(result.scalar_one_or_none())


async def _oldest_pending_job_days(session: AsyncSession) -> int | None:
    result = await session.execute(
        select(func.min(Job.created_at)).where(Job.status == JobStatus.PENDING_APPROVAL)  # pyright: ignore[reportArgumentType]
    )
    return _age_days(result.scalar_one_or_none())


async def _oldest_new_application_days(session: AsyncSession) -> int | None:
    result = await session.execute(
        select(func.min(Application.created_at)).where(
            Application.status == ApplicationStatus.NEW
        )  # pyright: ignore[reportArgumentType]
    )
    return _age_days(result.scalar_one_or_none())


async def _new_candidates_7d(session: AsyncSession) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    result = await session.execute(
        select(func.count())
        .select_from(CandidateProfile)
        .where(CandidateProfile.created_at >= cutoff)
    )
    return result.scalar_one()


async def _new_applications_7d(session: AsyncSession) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    result = await session.execute(
        select(func.count())
        .select_from(Application)
        .where(Application.created_at >= cutoff)
    )
    return result.scalar_one()


async def _recent_pending_companies(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(
            select(CompanyProfile.name, CompanyProfile.created_at)
            .join(User, User.id == CompanyProfile.user_id)  # pyright: ignore[reportArgumentType]
            .where(User.role == UserRole.COMPANY, User.is_active == False)  # noqa: E712
            .order_by(CompanyProfile.created_at.desc())
            .limit(RECENT_ITEMS_PER_TYPE)
        )
    ).all()
    return [
        {
            "type": "company",
            "label": r[0],
            "sublabel": None,
            "created_at": r[1].isoformat(),
        }  # noqa: E501
        for r in rows
    ]


async def _recent_pending_jobs(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(
            select(Job.title, CompanyProfile.name, Job.created_at)
            .join(CompanyProfile, Job.company_id == CompanyProfile.id)  # pyright: ignore[reportArgumentType]
            .where(Job.status == JobStatus.PENDING_APPROVAL)  # pyright: ignore[reportArgumentType]
            .order_by(Job.created_at.desc())
            .limit(RECENT_ITEMS_PER_TYPE)
        )
    ).all()
    return [
        {"type": "job", "label": r[0], "sublabel": r[1], "created_at": r[2].isoformat()}
        for r in rows
    ]


async def _application_trend_30d(session: AsyncSession) -> list[dict]:
    """Daily application counts for the last 30 days, zero-filled for empty days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=29)
    _day = literal_column("'day'")
    day_trunc = func.date_trunc(_day, Application.created_at)
    rows = (
        await session.execute(
            select(day_trunc.label("day"), func.count().label("n"))
            .where(Application.created_at >= cutoff)
            .group_by(day_trunc)
            .order_by(day_trunc)
        )
    ).all()
    counts: dict[date, int] = {}
    for row in rows:
        day_val = row[0]
        d = day_val.date() if hasattr(day_val, "date") else day_val
        counts[d] = row[1]
    today = datetime.now(timezone.utc).date()
    out = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        out.append({"date": d.isoformat(), "n": counts.get(d, 0)})
    return out


async def _recent_new_applications(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(
            select(CandidateProfile.full_name, Job.title, Application.created_at)
            .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)  # pyright: ignore[reportArgumentType]
            .join(Job, Application.job_id == Job.id)  # pyright: ignore[reportArgumentType]
            .where(Application.status == ApplicationStatus.NEW)  # pyright: ignore[reportArgumentType]
            .order_by(Application.created_at.desc())
            .limit(RECENT_ITEMS_PER_TYPE)
        )
    ).all()
    return [
        {
            "type": "application",
            "label": r[0],
            "sublabel": r[1],
            "created_at": r[2].isoformat(),
        }  # noqa: E501
        for r in rows
    ]
