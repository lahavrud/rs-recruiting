"""Admin overview: every scalar dashboard metric in one statement.

Split out of ``overview.py`` to keep it under the 300-line cap. Exercised
end-to-end via tests/services/admin/test_overview.py.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
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
from rs_shared.services.admin._filters import candidate_not_deleted


async def fetch_scalar_stats(session: AsyncSession) -> dict:
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
    # Inbox metrics drop tombstoned candidates so they match the lists they
    # link to (``candidate_not_deleted`` there too). Account deletion keeps the
    # Application rows and never moves their status, so without this a deleted
    # candidate's pending application sits in the badge forever. The historical
    # stats (status breakdown, 7d/30d application counts, top jobs) keep them:
    # those applications did happen.
    new_applications = (
        select(func.count())
        .select_from(Application)
        .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)  # pyright: ignore[reportArgumentType]
        .where(
            Application.status == ApplicationStatus.PENDING_ADMIN_REVIEW,  # pyright: ignore[reportArgumentType]
            candidate_not_deleted(),
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
        select(func.count())
        .select_from(CandidateProfile)
        .where(candidate_not_deleted())
        .scalar_subquery()
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
        .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)  # pyright: ignore[reportArgumentType]
        .where(
            Application.status == ApplicationStatus.PENDING_ADMIN_REVIEW,  # pyright: ignore[reportArgumentType]
            candidate_not_deleted(),
        )
        .scalar_subquery()
    )
    new_candidates_7d = (
        select(func.count())
        .select_from(CandidateProfile)
        .where(CandidateProfile.created_at >= cutoff_7d, candidate_not_deleted())
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
