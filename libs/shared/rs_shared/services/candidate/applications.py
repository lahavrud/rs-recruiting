"""Candidate-facing application listing, detail, edit, and withdraw (Sprint 11).

The candidate-facing API deliberately never exposes raw ``Application.status``
or ``admin_notes``. WITHDRAWN applications are filtered out entirely (the
candidate can re-apply per the partial unique index, so showing
a withdrawn row would be misleading — and the spec treats withdrawn rows as
if they don't exist for this candidate). Only the derived ``editable`` flag
(true iff ``status == NEW``) leaks across the boundary.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select

from rs_shared.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from rs_shared.core.infrastructure.storage_helpers import delete_file_best_effort
from rs_shared.core.services.storage import StorageProvider
from rs_shared.enums import ApplicationStatus, JobStatus
from rs_shared.models import Application, Job
from rs_shared.schemas.candidates import (
    CandidateApplicationDetail,
    CandidateApplicationJobDetail,
    CandidateApplicationJobSummary,
    CandidateApplicationListItem,
    CandidateApplicationMyAnswers,
    CandidateApplicationResumeMeta,
)
from rs_shared.services.exceptions import (
    ApplicationNotEditableError,
    ApplicationNotFoundError,
)
from rs_shared.services.public._application_helpers import validate_and_upload_resume
from rs_shared.services.utils.audit import record_audit_event

logger = logging.getLogger(__name__)


def _job_summary(job: Job) -> CandidateApplicationJobSummary:
    return CandidateApplicationJobSummary(
        id=job.id,  # type: ignore[arg-type]  # model id is int | None pre-flush; always set once persisted
        title=job.title,
        closed=job.status == JobStatus.CLOSED,
    )


def _job_detail(job: Job) -> CandidateApplicationJobDetail:
    return CandidateApplicationJobDetail(
        id=job.id,  # type: ignore[arg-type]  # model id is int | None pre-flush; always set once persisted
        title=job.title,
        description=job.description,
        closed=job.status == JobStatus.CLOSED,
    )


def _list_item(app: Application) -> CandidateApplicationListItem:
    return CandidateApplicationListItem(
        id=app.id,  # type: ignore[arg-type]  # model id is int | None pre-flush; always set once persisted
        submitted_at=app.created_at,
        editable=app.status == ApplicationStatus.NEW,
        job=_job_summary(app.job),
    )


async def list_my_applications(
    session: AsyncSession,
    *,
    candidate_id: int,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[CandidateApplicationListItem]:
    """One page of this candidate's applications, newest first.

    WITHDRAWN rows are excluded — they are invisible to the candidate via
    this endpoint, mirroring the issue's "withdrawn behaves like deleted"
    semantics.
    """
    page_size = clamp_limit(limit)
    query = select(Application).where(
        Application.candidate_id == candidate_id,  # pyright: ignore[reportArgumentType]
        Application.status != ApplicationStatus.WITHDRAWN,  # pyright: ignore[reportArgumentType]
    )
    query = query.options(selectinload(Application.job))
    query = apply_cursor(
        query,
        sort_col=Application.created_at,
        id_col=Application.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
    )
    rows = list((await session.execute(query)).scalars().all())
    return build_cursor_page(
        rows,
        serializer=_list_item,
        cursor_key=lambda a: (a.created_at, a.id),  # type: ignore[arg-type,return-value]  # SQLAlchemy column attrs in a plain tuple lambda; stubs incomplete
        limit=page_size,
    )


async def get_my_application(
    session: AsyncSession,
    *,
    candidate_id: int,
    application_id: int,
) -> CandidateApplicationDetail:
    """Return one application — 404 if foreign or WITHDRAWN.

    Raises ApplicationNotFoundError on miss; the router maps it to a 404 HTTP
    response. Foreign-id and withdrawn-row cases collapse to the same 404
    so the endpoint can't be used to probe other candidates' application IDs.
    """
    query = (
        select(Application)
        .options(selectinload(Application.job))
        .where(
            Application.id == application_id,  # pyright: ignore[reportArgumentType]
            Application.candidate_id == candidate_id,  # pyright: ignore[reportArgumentType]
            Application.status != ApplicationStatus.WITHDRAWN,  # pyright: ignore[reportArgumentType]
        )
    )
    app = (await session.execute(query)).scalar_one_or_none()
    if app is None:
        raise ApplicationNotFoundError("Application not found")
    return _build_detail(app)


async def get_application_resume_key(
    session: AsyncSession,
    *,
    candidate_id: int,
    application_id: int,
) -> str:
    """Return the snapshotted resume's storage key for streaming.

    Raises ApplicationNotFoundError if the application is foreign, withdrawn, or
    has no resume snapshot — all three cases share a single 404 so callers
    can't probe ownership or existence separately.
    """
    query = select(Application).where(
        Application.id == application_id,  # pyright: ignore[reportArgumentType]
        Application.candidate_id == candidate_id,  # pyright: ignore[reportArgumentType]
        Application.status != ApplicationStatus.WITHDRAWN,  # pyright: ignore[reportArgumentType]
    )
    app = (await session.execute(query)).scalar_one_or_none()
    if app is None or not app.resume_path:
        raise ApplicationNotFoundError("Resume not found")
    return app.resume_path


def _build_detail(app: Application) -> CandidateApplicationDetail:
    """Build a CandidateApplicationDetail from a loaded Application row.

    Requires app.job to be eagerly loaded.
    """
    resume: CandidateApplicationResumeMeta | None = None
    if app.resume_path:
        resume = CandidateApplicationResumeMeta(
            filename=app.resume_filename or app.resume_path.rsplit("/", 1)[-1],
            snapshot_present=True,
        )
    return CandidateApplicationDetail(
        id=app.id,  # type: ignore[arg-type]  # model id is int | None pre-flush; always set once persisted
        submitted_at=app.created_at,
        editable=app.status == ApplicationStatus.NEW,
        job=_job_detail(app.job),
        my_answers=CandidateApplicationMyAnswers(
            service_concept=app.service_concept,
            salary_expectations=app.salary_expectations,
            strength=app.strength,
            growth_area=app.growth_area,
        ),
        resume=resume,
    )


@dataclass(frozen=True)
class ApplicationEditData:
    service_concept: str | None
    salary_expectations: str | None
    strength: str | None
    growth_area: str | None
    resume_bytes: bytes | None
    resume_filename: str | None


async def edit_my_application(
    session: AsyncSession,
    *,
    candidate_id: int,
    application_id: int,
    data: ApplicationEditData,
    storage: StorageProvider,
) -> CandidateApplicationDetail:
    """Partially update text answers and/or replace the resume snapshot.

    Gates: foreign/non-existent → 404, WITHDRAWN → 404, non-NEW → 409.
    Empty-body (no text fields, no resume) → ValueError so the router can
    return 400 without special-casing service exceptions.
    """
    query = (
        select(Application)
        .options(selectinload(Application.job))
        .where(
            Application.id == application_id,  # pyright: ignore[reportArgumentType]
            Application.candidate_id == candidate_id,  # pyright: ignore[reportArgumentType]
        )
    )
    app = (await session.execute(query)).scalar_one_or_none()
    if app is None:
        raise ApplicationNotFoundError("Application not found")
    if app.status == ApplicationStatus.WITHDRAWN:
        raise ApplicationNotFoundError("Application not found")
    if app.status != ApplicationStatus.NEW:
        raise ApplicationNotEditableError("Application is no longer editable")

    has_text = any(
        f is not None
        for f in (
            data.service_concept,
            data.salary_expectations,
            data.strength,
            data.growth_area,
        )
    )
    if not has_text and data.resume_bytes is None:
        raise ValueError("empty_body")

    if data.service_concept is not None:
        app.service_concept = data.service_concept
    if data.salary_expectations is not None:
        app.salary_expectations = data.salary_expectations
    if data.strength is not None:
        app.strength = data.strength
    if data.growth_area is not None:
        app.growth_area = data.growth_area

    old_resume_key: str | None = None
    if data.resume_bytes is not None and data.resume_filename is not None:
        new_key, new_hash = await validate_and_upload_resume(
            data.resume_bytes, data.resume_filename, storage
        )
        old_resume_key = app.resume_path
        app.resume_path = new_key
        app.resume_filename = data.resume_filename
        app.resume_hash = new_hash

    await session.commit()

    if old_resume_key and old_resume_key != app.resume_path:
        await delete_file_best_effort(
            storage, old_resume_key, logger, context="old resume snapshot"
        )

    return _build_detail(app)


async def withdraw_my_application(
    session: AsyncSession,
    *,
    candidate_id: int,
    application_id: int,
    actor_user_id: int,
    ip_address: str | None = None,
) -> None:
    """Set the application status to WITHDRAWN.

    Gates: foreign/non-existent → 404, already WITHDRAWN → 404, non-NEW → 409.
    The row is preserved for admin visibility; only the candidate's list
    filters it out.
    """
    query = select(Application).where(
        Application.id == application_id,  # pyright: ignore[reportArgumentType]
        Application.candidate_id == candidate_id,  # pyright: ignore[reportArgumentType]
    )
    app = (await session.execute(query)).scalar_one_or_none()
    if app is None:
        raise ApplicationNotFoundError("Application not found")
    if app.status == ApplicationStatus.WITHDRAWN:
        raise ApplicationNotFoundError("Application not found")
    if app.status != ApplicationStatus.NEW:
        raise ApplicationNotEditableError("Application is no longer editable")

    old_status = app.status
    app.status = ApplicationStatus.WITHDRAWN
    await session.flush()

    await record_audit_event(
        session,
        actor_user_id=actor_user_id,
        action="application.status_change",
        target_type="Application",
        target_id=application_id,
        detail=f"{old_status.value}->{ApplicationStatus.WITHDRAWN.value}",
        ip_address=ip_address,
    )

    await session.commit()
