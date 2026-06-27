"""Application management sub-module for company job service."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.core.matching import cosine_similarity_score
from src.enums import ApplicationStatus
from src.models import Application, CandidateProfile, Job
from src.schemas.companies import (
    CompanyApplicationCandidateRead,
    CompanyApplicationRead,
)
from src.services.exceptions import (
    ApplicationNotFoundError,
    InvalidApplicationStatusTransitionError,
    JobNotFoundError,
    JobNotOwnedByCompanyError,
)

_COMPANY_VISIBLE_STATUSES = frozenset(
    {
        ApplicationStatus.APPROVED_BY_ADMIN,
        ApplicationStatus.HIRED,
        ApplicationStatus.REJECTED,
    }
)

_COMPANY_ALLOWED_STATUSES = frozenset(
    {ApplicationStatus.HIRED, ApplicationStatus.REJECTED}
)


async def list_job_applications(
    job_id: int,
    company_id: int,
    session: AsyncSession,
) -> list[CompanyApplicationRead]:
    """Return all applications for a job owned by the given company.

    Raises:
        JobNotFoundError: If job not found
        JobNotOwnedByCompanyError: If job is not owned by the company
    """
    job = await get_by_id_or_raise(
        session, Job, job_id, lambda pk: JobNotFoundError(f"Job with ID {pk} not found")
    )
    if job.company_id != company_id:
        raise JobNotOwnedByCompanyError(
            f"Job {job_id} is not owned by company {company_id}"
        )

    apps = list(
        (
            await session.execute(
                select(Application)
                .options(selectinload(Application.candidate))  # pyright: ignore[reportArgumentType]
                .where(
                    Application.job_id == job_id,  # pyright: ignore[reportArgumentType]
                    Application.status.in_(_COMPANY_VISIBLE_STATUSES),  # pyright: ignore[reportArgumentType]
                )
                .order_by(Application.created_at.desc())  # pyright: ignore[reportArgumentType]
            )
        )
        .scalars()
        .all()
    )

    scores: dict[int, float] = {}
    if job.embedding is not None and apps:
        candidate_ids = [a.candidate_id for a in apps]
        distance_expr = CandidateProfile.embedding.cosine_distance(job.embedding)
        score_rows = list(
            (
                await session.execute(
                    select(CandidateProfile.id, distance_expr.label("dist")).where(  # pyright: ignore[reportArgumentType]
                        CandidateProfile.id.in_(candidate_ids),  # pyright: ignore[reportArgumentType]
                        CandidateProfile.embedding.is_not(None),  # pyright: ignore[reportArgumentType]
                    )
                )
            ).all()
        )
        for cid, dist in score_rows:
            scores[cid] = cosine_similarity_score(dist)

    return [
        CompanyApplicationRead(
            id=app.id or 0,
            job_id=app.job_id,
            candidate_id=app.candidate_id,
            status=app.status.value,
            created_at=app.created_at,
            updated_at=app.updated_at,
            match_score=scores.get(app.candidate_id),
            ai_review=app.candidate.resume_summary,
            candidate=CompanyApplicationCandidateRead(
                id=app.candidate.id or 0,
                full_name=app.candidate.full_name,
                email=app.candidate.email,
                phone=app.candidate.phone,
            ),
        )
        for app in apps
    ]


async def update_application_status(
    job_id: int,
    application_id: int,
    new_status: str,
    company_id: int,
    session: AsyncSession,
) -> CompanyApplicationRead:
    """Update the status of an application on a job owned by this company.

    Companies may only move applications to HIRED or REJECTED.

    Raises:
        InvalidApplicationStatusTransitionError: Target status not allowed for companies
        JobNotFoundError: If job not found
        JobNotOwnedByCompanyError: If job is not owned by the company
        ApplicationNotFoundError: If application not found for this job
    """
    try:
        target = ApplicationStatus(new_status)
    except ValueError as exc:
        raise InvalidApplicationStatusTransitionError(
            f"Unknown status: {new_status}"
        ) from exc

    if target not in _COMPANY_ALLOWED_STATUSES:
        raise InvalidApplicationStatusTransitionError(
            f"Companies cannot set status to {new_status}"
        )

    job = await get_by_id_or_raise(
        session, Job, job_id, lambda pk: JobNotFoundError(f"Job with ID {pk} not found")
    )
    if job.company_id != company_id:
        raise JobNotOwnedByCompanyError(
            f"Job {job_id} is not owned by company {company_id}"
        )

    app = (
        await session.execute(
            select(Application)
            .options(selectinload(Application.candidate))  # pyright: ignore[reportArgumentType]
            .where(
                Application.id == application_id,  # pyright: ignore[reportArgumentType]
                Application.job_id == job_id,  # pyright: ignore[reportArgumentType]
            )
        )
    ).scalar_one_or_none()
    if app is None:
        raise ApplicationNotFoundError(
            f"Application {application_id} not found for job {job_id}"
        )

    app.status = target
    app.updated_at = datetime.now(timezone.utc)
    await session.flush()

    score: float | None = None
    if job.embedding is not None and app.candidate.embedding is not None:
        distance_expr = CandidateProfile.embedding.cosine_distance(job.embedding)
        row = (
            await session.execute(
                select(distance_expr.label("dist")).where(  # pyright: ignore[reportArgumentType]
                    CandidateProfile.id == app.candidate_id
                )  # pyright: ignore[reportArgumentType]
            )
        ).one_or_none()
        if row is not None:
            score = cosine_similarity_score(row.dist)

    return CompanyApplicationRead(
        id=app.id or 0,
        job_id=app.job_id,
        candidate_id=app.candidate_id,
        status=str(app.status),
        created_at=app.created_at,
        updated_at=app.updated_at,
        match_score=score,
        ai_review=app.candidate.resume_summary,
        candidate=CompanyApplicationCandidateRead(
            id=app.candidate.id or 0,
            full_name=app.candidate.full_name,
            email=app.candidate.email,
            phone=app.candidate.phone,
        ),
    )
