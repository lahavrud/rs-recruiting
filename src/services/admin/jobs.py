"""Admin service layer for direct job CRUD.

Separate from `jobs_admin.py` (approval workflow) — these functions let
an admin manage any job in any status, including creating jobs directly
on behalf of a company that hasn't been onboarded yet.
"""

from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import case, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.config import settings
from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.core.infrastructure.pagination import (
    CursorPage,
    SortValue,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.core.infrastructure.transactions import defer_after_commit
from src.core.matching import cosine_similarity_score
from src.core.tasks import enqueue_embed_job_task
from src.enums import JobStatus
from src.models import Application, CandidateProfile, CompanyProfile, Job
from src.schemas import (
    CandidateProfileRead,
    JobAdminCreate,
    JobAdminUpdate,
    JobCandidateMatchRead,
    JobRead,
)
from src.services.admin._job_close import close_active_applications
from src.services.admin._job_emails import FIELD_LABELS, notify_company_of_update
from src.services.exceptions import CompanyNotFoundError, JobNotFoundError

JobSortColumn = Literal["name", "created_at", "status"]

_STATUS_PRIORITY: dict[JobStatus, int] = {
    JobStatus.PENDING_APPROVAL: 0,
    JobStatus.PUBLISHED: 1,
    JobStatus.CLOSED: 2,
}


def _sort_column(column: JobSortColumn) -> Any:
    if column == "name":
        return Job.title
    if column == "status":
        return case(
            *[(Job.status == k, v) for k, v in _STATUS_PRIORITY.items()],
            else_=len(_STATUS_PRIORITY),
        )
    return Job.created_at


def _sort_value(job: Job, column: JobSortColumn) -> SortValue:
    if column == "name":
        return job.title
    if column == "status":
        return _STATUS_PRIORITY.get(job.status, len(_STATUS_PRIORITY))
    return job.created_at


# Job fields that feed the matching embedding (see cv_extraction.job_embedding_text).
# A change to any of these on a PUBLISHED job warrants a re-embed.
_EMBEDDABLE_FIELDS = frozenset(
    {"title", "short_description", "description", "requirements", "tags", "location"}
)


async def list_jobs(
    session: AsyncSession,
    *,
    status: JobStatus | None = None,
    company_id: int | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
    sort: JobSortColumn = "created_at",
    order: Literal["asc", "desc"] = "desc",
    sort2: JobSortColumn | None = None,
    order2: Literal["asc", "desc"] = "desc",
) -> CursorPage[JobRead]:
    """One page of jobs across all statuses, sorted by `sort`/`order`.

    `status` filters to a single status when provided (None returns all).
    `company_id` filters to jobs belonging to a specific company.
    `q` searches job title (case-insensitive substring match).
    `sort="name"` sorts by the job title.
    `sort="status"` groups by status priority — PENDING_APPROVAL first when
    `order="asc"`, CLOSED first when `order="desc"`.
    `sort2` adds a tiebreaker column within each primary group (e.g.
    `sort="status"` with `sort2="created_at"` groups by status, then by date).
    """
    if sort2 == sort:
        sort2 = None
    page_size = clamp_limit(limit)
    base = select(Job).options(selectinload(Job.company))
    if status is not None:
        base = base.where(Job.status == status)  # pyright: ignore[reportArgumentType]
    if company_id is not None:
        base = base.where(Job.company_id == company_id)  # pyright: ignore[reportArgumentType]
    if q:
        base = base.where(Job.title.icontains(q))  # pyright: ignore[reportArgumentType]

    sort_col = _sort_column(sort)
    secondary_col = _sort_column(sort2) if sort2 is not None else None
    sort_key = sort if sort2 is None else f"{sort},{sort2}"

    query = apply_cursor(
        base,
        sort_col=sort_col,  # pyright: ignore[reportArgumentType]
        id_col=Job.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
        sort_key=sort_key,
        direction=order,
        secondary_col=secondary_col,  # pyright: ignore[reportArgumentType]
        secondary_direction=order2,
    )
    rows = list((await session.execute(query)).scalars().all())

    def _cursor_key(
        j: Job,
    ) -> tuple[SortValue, int] | tuple[SortValue, SortValue | None, int]:
        if sort2 is not None:
            return _sort_value(j, sort), _sort_value(j, sort2), j.id
        return _sort_value(j, sort), j.id

    return build_cursor_page(
        rows,
        serializer=JobRead.model_validate,
        cursor_key=_cursor_key,
        limit=page_size,
        sort_key=sort_key,
    )


async def get_job_candidate_matches(
    job_id: int, session: AsyncSession
) -> list[JobCandidateMatchRead]:
    """Live-ranked candidates for a job, best score first.

    Computed on demand (cosine distance) against every embedded candidate —
    mirrors ``services.admin.candidates.get_candidate_job_matches``, the
    reverse direction.

    Raises ``JobNotFoundError`` if the job doesn't exist. Returns an empty
    list if the job isn't PUBLISHED or has no embedding yet.
    """
    job = await get_by_id_or_raise(
        session, Job, job_id, lambda pk: JobNotFoundError(f"Job {pk} not found")
    )
    if job.status != JobStatus.PUBLISHED or job.embedding is None:
        return []

    distance = CandidateProfile.embedding.cosine_distance(job.embedding)
    rows = (
        await session.execute(
            select(CandidateProfile, distance.label("distance"))
            .where(CandidateProfile.embedding.is_not(None))
            .order_by(distance)
            .limit(settings.embedding_top_matches)
        )
    ).all()
    return [
        JobCandidateMatchRead(
            candidate=CandidateProfileRead.model_validate(candidate),
            score=cosine_similarity_score(dist),
        )
        for candidate, dist in rows
    ]


async def admin_create_job(data: JobAdminCreate, session: AsyncSession) -> JobRead:
    """Create a job directly under an existing company profile.

    Raises:
        CompanyNotFoundError: If the referenced `company_id` does not exist.
    """
    await get_by_id_or_raise(
        session,
        CompanyProfile,
        data.company_id,
        lambda pk: CompanyNotFoundError(f"Company profile {pk} not found"),
    )

    job = Job(
        company_id=data.company_id,
        title=data.title,
        short_description=data.short_description,
        description=data.description,
        requirements=[r.model_dump() for r in data.requirements],
        tags=list(data.tags),
        is_featured=data.is_featured,
        location=data.location,
        salary_min=data.salary_min,
        salary_max=data.salary_max,
        status=data.status,
    )
    session.add(job)
    await session.flush()
    await session.refresh(job, attribute_names=["company"])
    return JobRead.model_validate(job)


async def update_job(
    job_id: int,
    data: JobAdminUpdate,
    session: AsyncSession,
    *,
    actor_user_id: int | None = None,
) -> JobRead:
    """Apply a partial update to a job. Admin can edit any field at any status.

    Notifies the company by email when at least one field changes and the
    company has an attached user account. Admin-created orphan companies
    (no user) are silently skipped.

    Raises:
        JobNotFoundError: If no job with that id exists.
    """
    result = await session.execute(
        select(Job)
        .options(selectinload(Job.company).selectinload(CompanyProfile.user))
        .where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundError(f"Job {job_id} not found")

    # model_dump serializes nested pydantic items (e.g. JobRequirementItem)
    # to plain dicts, which is exactly what the JSONB column wants.
    payload = data.model_dump(exclude_unset=True)

    changed_labels = [
        FIELD_LABELS.get(field, field)
        for field, value in payload.items()
        if getattr(job, field) != value
    ]
    old_title = job.title
    old_status = job.status
    title_changed = "title" in payload and payload["title"] != old_title

    for field, value in payload.items():
        setattr(job, field, value)
    job.updated_at = datetime.now(timezone.utc)

    await session.flush()

    is_closing = old_status == JobStatus.PUBLISHED and job.status == JobStatus.CLOSED

    notify_company_of_update(
        job,
        old_title=old_title,
        title_changed=title_changed,
        changed_labels=changed_labels,
        is_closing=is_closing,
    )

    # When a published job is closed, notify all active applicants and
    # transition their applications to JOB_CLOSED.
    if is_closing:
        await close_active_applications(
            job_id, job.title, session, actor_user_id=actor_user_id
        )

    # Re-embed when a published job's matchable text changed, so candidate
    # matches rank against the current content (after commit).
    if job.status == JobStatus.PUBLISHED and _EMBEDDABLE_FIELDS & payload.keys():
        embed_job_id = job.id
        defer_after_commit(lambda: enqueue_embed_job_task(embed_job_id))

    await session.refresh(job, attribute_names=["company"])
    return JobRead.model_validate(job)


async def delete_job(job_id: int, session: AsyncSession) -> None:
    """Hard-delete a job and cascade through its applications.

    Candidate profiles and resume files are preserved — they belong to the
    candidate, not the job.

    Raises:
        JobNotFoundError: If no job with that id exists.
    """
    job = await get_by_id_or_raise(
        session, Job, job_id, lambda pk: JobNotFoundError(f"Job {pk} not found")
    )

    await session.execute(
        delete(Application).where(Application.job_id == job_id)  # pyright: ignore[reportArgumentType]
    )
    await session.delete(job)
    await session.flush()
