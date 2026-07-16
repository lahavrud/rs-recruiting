"""Admin overview aggregation — real counts replacing capped page-length heuristics."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import (
    String,
    cast,
    func,
    literal,
    literal_column,
    null,
    select,
    union_all,
)
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.enums import ApplicationStatus, InviteTokenStatus, JobStatus, UserRole
from rs_shared.models import (
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
    """Compute all admin dashboard counts on the shared session.

    Queries run sequentially — asyncio.gather() with a shared AsyncSession is
    not safe (SQLAlchemy's session is not designed for concurrent coroutine
    access and deadlocks against its own internal connection mutex) — so the
    lever on this request path is fewer round-trips: all scalar aggregates go
    in one statement, leaving only the shaped result sets as separate queries.
    """
    scalars = await _fetch_scalar_stats(session)
    status_counts = await _count_application_statuses(session)
    top_jobs = await _top_jobs_by_applications(session)
    all_recent = await _fetch_recent_items(session)
    trend_30d = await _application_trend_30d(session)

    return {
        "inbox": {
            "pending_invites": scalars["pending_invites"],
            "pending_companies": scalars["pending_companies"],
            "pending_jobs": scalars["pending_jobs"],
            "new_applications": scalars["new_applications"],
            "oldest_pending_company_days": _age_days(scalars["oldest_company_at"]),
            "oldest_pending_job_days": _age_days(scalars["oldest_job_at"]),
            "oldest_new_application_days": _age_days(scalars["oldest_application_at"]),
        },
        "stats": {
            "active_companies": scalars["active_companies"],
            "published_jobs": scalars["published_jobs"],
            "total_candidates": scalars["total_candidates"],
            "application_status_counts": status_counts,
            "top_jobs": top_jobs,
        },
        "pulse": {
            "new_candidates_7d": scalars["new_candidates_7d"],
            "new_applications_7d": scalars["new_applications_7d"],
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


async def _fetch_scalar_stats(session: AsyncSession) -> dict:
    """All scalar aggregates (counts, oldest timestamps, 7-day counts) in one
    statement — a single DB round-trip instead of twelve.

    get_overview runs on the admin dashboard's request path; before this the
    sequential per-metric queries dominated the endpoint's latency. Each metric
    is a scalar subquery, so per-metric filters read the same as they did as
    standalone queries.
    """
    cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)

    pending_invites = (
        select(func.count())
        .select_from(InviteToken)
        .where(
            InviteToken.status == InviteTokenStatus.PENDING  # pyright: ignore[reportArgumentType]
        )
        .scalar_subquery()
    )
    pending_companies = (
        select(func.count())
        .select_from(User)
        .join(CompanyProfile, User.id == CompanyProfile.user_id)  # pyright: ignore[reportArgumentType]
        .where(User.role == UserRole.COMPANY, User.is_active == False)  # noqa: E712
        .scalar_subquery()
    )
    pending_jobs = (
        select(func.count())
        .select_from(Job)
        .where(
            Job.status == JobStatus.PENDING_APPROVAL  # pyright: ignore[reportArgumentType]
        )
        .scalar_subquery()
    )
    new_applications = (
        select(func.count())
        .select_from(Application)
        .where(
            Application.status == ApplicationStatus.PENDING_ADMIN_REVIEW  # pyright: ignore[reportArgumentType]
        )
        .scalar_subquery()
    )
    active_companies = (
        select(func.count())
        .select_from(CompanyProfile)
        .outerjoin(User, CompanyProfile.user_id == User.id)  # pyright: ignore[reportArgumentType]
        .where(
            (CompanyProfile.user_id == None)  # noqa: E711
            | (  # pyright: ignore[reportOperatorIssue]
                (User.role == UserRole.COMPANY) & (User.is_active == True)  # noqa: E712
            )
        )
        .scalar_subquery()
    )
    published_jobs = (
        select(func.count())
        .select_from(Job)
        .where(
            Job.status == JobStatus.PUBLISHED  # pyright: ignore[reportArgumentType]
        )
        .scalar_subquery()
    )
    total_candidates = (
        select(func.count()).select_from(CandidateProfile).scalar_subquery()
    )
    oldest_company_at = (
        select(func.min(CompanyProfile.created_at))
        .join(User, User.id == CompanyProfile.user_id)  # pyright: ignore[reportArgumentType]
        .where(User.role == UserRole.COMPANY, User.is_active == False)  # noqa: E712
        .scalar_subquery()
    )
    oldest_job_at = (
        select(func.min(Job.created_at))
        .where(Job.status == JobStatus.PENDING_APPROVAL)  # pyright: ignore[reportArgumentType]
        .scalar_subquery()
    )
    oldest_application_at = (
        select(func.min(Application.created_at))
        .where(
            Application.status == ApplicationStatus.PENDING_ADMIN_REVIEW  # pyright: ignore[reportArgumentType]
        )
        .scalar_subquery()
    )
    new_candidates_7d = (
        select(func.count())
        .select_from(CandidateProfile)
        .where(CandidateProfile.created_at >= cutoff_7d)
        .scalar_subquery()
    )
    new_applications_7d = (
        select(func.count())
        .select_from(Application)
        .where(Application.created_at >= cutoff_7d)
        .scalar_subquery()
    )

    row = (
        await session.execute(
            select(
                pending_invites.label("pending_invites"),
                pending_companies.label("pending_companies"),
                pending_jobs.label("pending_jobs"),
                new_applications.label("new_applications"),
                active_companies.label("active_companies"),
                published_jobs.label("published_jobs"),
                total_candidates.label("total_candidates"),
                oldest_company_at.label("oldest_company_at"),
                oldest_job_at.label("oldest_job_at"),
                oldest_application_at.label("oldest_application_at"),
                new_candidates_7d.label("new_candidates_7d"),
                new_applications_7d.label("new_applications_7d"),
            )
        )
    ).one()
    return dict(row._mapping)


async def _count_application_statuses(session: AsyncSession) -> dict[str, int]:
    rows = (
        await session.execute(
            select(Application.status, func.count().label("n")).group_by(
                Application.status
            )  # pyright: ignore[reportArgumentType]
        )
    ).all()
    # Key by the enum *value* ("PENDING_ADMIN_REVIEW"). str(member) would yield
    # "ApplicationStatus.PENDING_ADMIN_REVIEW", which the frontend's status-keyed
    # lookups miss, leaving every status in the breakdown stuck at 0.
    return {row[0].value: row[1] for row in rows}


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


async def _fetch_recent_items(session: AsyncSession) -> list[dict]:
    """The three 'recent' feeds (pending companies, pending jobs, new
    applications) as one UNION ALL — a single round-trip instead of three.

    Each branch keeps its own ORDER BY + LIMIT (compiled parenthesized), so
    the DB does the per-type top-N; the cross-type merge order is applied by
    the caller's sort. Returned newest-first across all types.
    """
    companies = (
        select(
            literal("company").label("item_type"),
            CompanyProfile.name.label("label"),
            cast(null(), String).label("sublabel"),
            CompanyProfile.created_at.label("created_at"),
        )
        .join(User, User.id == CompanyProfile.user_id)  # pyright: ignore[reportArgumentType]
        .where(User.role == UserRole.COMPANY, User.is_active == False)  # noqa: E712
        .order_by(CompanyProfile.created_at.desc())
        .limit(RECENT_ITEMS_PER_TYPE)
    )
    jobs = (
        select(
            literal("job").label("item_type"),
            Job.title.label("label"),
            CompanyProfile.name.label("sublabel"),
            Job.created_at.label("created_at"),
        )
        .join(CompanyProfile, Job.company_id == CompanyProfile.id)  # pyright: ignore[reportArgumentType]
        .where(Job.status == JobStatus.PENDING_APPROVAL)  # pyright: ignore[reportArgumentType]
        .order_by(Job.created_at.desc())
        .limit(RECENT_ITEMS_PER_TYPE)
    )
    applications = (
        select(
            literal("application").label("item_type"),
            CandidateProfile.full_name.label("label"),
            Job.title.label("sublabel"),
            Application.created_at.label("created_at"),
        )
        .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)  # pyright: ignore[reportArgumentType]
        .join(Job, Application.job_id == Job.id)  # pyright: ignore[reportArgumentType]
        .where(Application.status == ApplicationStatus.PENDING_ADMIN_REVIEW)  # pyright: ignore[reportArgumentType]
        .order_by(Application.created_at.desc())
        .limit(RECENT_ITEMS_PER_TYPE)
    )

    rows = (await session.execute(union_all(companies, jobs, applications))).all()
    items = [
        {
            "type": r[0],
            "label": r[1],
            "sublabel": r[2],
            "created_at": r[3].isoformat(),
        }
        for r in rows
    ]
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items


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
