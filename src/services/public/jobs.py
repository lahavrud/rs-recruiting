"""Public job board service functions (no authentication required)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.enums import ApplicationStatus, JobStatus, UserRole
from src.models import Application, CandidateProfile, Job, User
from src.schemas import JobPublicRead
from src.schemas.jobs import MyApplicationInfo
from src.services.exceptions import JobNotFoundError


async def list_published_jobs(
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[JobPublicRead]:
    """One page of published jobs, featured first then newest.

    Featured-first is applied as a leading order term so that within any
    given page, featured jobs surface at the top. The cursor still encodes
    only `(created_at, id)` — for the typical small public board where page
    one covers all (or nearly all) jobs, this gives the intended UX.
    """
    page_size = clamp_limit(limit)
    base = (
        select(Job)
        .where(Job.status == JobStatus.PUBLISHED)  # pyright: ignore[reportArgumentType]
        .order_by(Job.is_featured.desc())  # pyright: ignore[reportArgumentType]
    )
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
        serializer=JobPublicRead.model_validate,
        cursor_key=lambda j: (j.created_at, j.id),
        limit=page_size,
    )


async def get_published_job(
    job_id: int,
    session: AsyncSession,
    *,
    current_user: User | None = None,
) -> JobPublicRead:
    """When `current_user` is an authenticated candidate, populates
    `my_application` with their own non-WITHDRAWN application for this job
    (if any), so the frontend can show "already applied" / edit affordances
    without a second request.

    Raises:
        JobNotFoundError: If job not found or not published
    """
    job = await get_by_id_or_raise(
        session, Job, job_id, lambda pk: JobNotFoundError(f"Job with ID {pk} not found")
    )
    if job.status != JobStatus.PUBLISHED:
        raise JobNotFoundError(f"Job with ID {job_id} is not published")

    job_read = JobPublicRead.model_validate(job)

    if current_user is not None and current_user.role == UserRole.CANDIDATE:
        # Find this candidate's most-relevant non-WITHDRAWN application for
        # the job (in practice there's at most one — the partial unique
        # index enforces it).
        my_app = (
            await session.execute(
                select(Application)
                .join(
                    CandidateProfile,
                    CandidateProfile.id == Application.candidate_id,  # type: ignore[arg-type]
                )
                .where(  # pyright: ignore[reportArgumentType]
                    Application.job_id == job_id,
                    CandidateProfile.user_id == current_user.id,
                    Application.status != ApplicationStatus.WITHDRAWN,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if my_app is not None:
            assert my_app.id is not None
            job_read.my_application = MyApplicationInfo(
                id=my_app.id,
                editable=my_app.status == ApplicationStatus.NEW,
            )

    return job_read


async def get_published_job_orm(job_id: int, session: AsyncSession) -> Job | None:
    """Get a published job by ID as the raw ORM object, for SEO prerendering."""
    return (
        await session.execute(
            select(Job).where(  # pyright: ignore[reportArgumentType]
                Job.id == job_id, Job.status == JobStatus.PUBLISHED
            )
        )
    ).scalar_one_or_none()


async def list_featured_published_jobs(
    session: AsyncSession, *, limit: int
) -> list[Job]:
    """Published jobs, featured first then newest, as raw ORM objects.

    For SEO prerendering (`/api/og/home`, `/api/og/jobs`), which renders
    full `Job` fields rather than the public-board's restricted schema.
    """
    result = await session.execute(
        select(Job)
        .where(Job.status == JobStatus.PUBLISHED)  # pyright: ignore[reportArgumentType]
        .order_by(Job.is_featured.desc(), Job.created_at.desc())  # pyright: ignore[reportAttributeAccessIssue]
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_published_job_sitemap_entries(
    session: AsyncSession,
) -> list[tuple[int, datetime | None]]:
    """`(id, updated_at)` for every published job, for sitemap.xml generation."""
    result = await session.execute(
        select(Job.id, Job.updated_at).where(Job.status == JobStatus.PUBLISHED)  # pyright: ignore[reportArgumentType]
    )
    return list(result.all())
