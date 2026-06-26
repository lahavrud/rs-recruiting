"""Admin overview aggregation — real counts replacing capped page-length heuristics."""

import asyncio

from sqlalchemy import func, select
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


async def get_overview(session: AsyncSession) -> dict:
    """Compute all admin dashboard counts in parallel."""
    results = await asyncio.gather(
        _count_pending_invites(session),
        _count_pending_companies(session),
        _count_pending_jobs(session),
        _count_new_applications(session),
        _count_active_companies(session),
        _count_published_jobs(session),
        _count_candidates(session),
        _count_application_statuses(session),
        _top_jobs_by_applications(session),
    )
    (
        pending_invites,
        pending_companies,
        pending_jobs,
        new_applications,
        active_companies,
        published_jobs,
        total_candidates,
        status_counts,
        top_jobs,
    ) = results

    return {
        "inbox": {
            "pending_invites": pending_invites,
            "pending_companies": pending_companies,
            "pending_jobs": pending_jobs,
            "new_applications": new_applications,
        },
        "stats": {
            "active_companies": active_companies,
            "published_jobs": published_jobs,
            "total_candidates": total_candidates,
            "application_status_counts": status_counts,
            "top_jobs": top_jobs,
        },
    }


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
