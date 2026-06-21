"""Authenticated candidate application endpoints.

Lists, detail, resume-snapshot streaming, edit, and withdraw for the
authenticated candidate's own applications. Status and admin_notes are
intentionally not exposed; the only state signal sent back is the derived
``editable`` flag (true iff status == NEW).
"""

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api._resume_streaming import basename_from_storage_key, stream_resume
from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_candidate
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    CursorPage,
)
from src.core.services.file_validation import validate_upload
from src.core.services.storage import get_storage_provider
from src.models import CandidateProfile, User
from src.schemas import (
    CandidateApplicationDetail,
    CandidateApplicationListItem,
)
from src.services.candidate.applications import (
    ApplicationEditData,
    edit_my_application,
    get_application_resume_key,
    get_my_application,
    list_my_applications,
    withdraw_my_application,
)
from src.services.exceptions import (
    ApplicationNotEditableError,
    ApplicationNotFoundError,
    InvalidCursorError,
)

_RESUME_ALLOWED_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)
_RESUME_MAX_BYTES = 10 * 1024 * 1024

router = APIRouter(prefix="/api/candidate/me/applications", tags=["candidate"])


@router.get("", response_model=CursorPage[CandidateApplicationListItem])
async def list_applications(
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    current: tuple[User, CandidateProfile] = Depends(get_current_candidate),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[CandidateApplicationListItem]:
    """List the authenticated candidate's applications, newest first.

    Excludes WITHDRAWN rows (invisible per the issue's semantics).
    """
    _, profile = current
    try:
        return await list_my_applications(
            session,
            candidate_id=profile.id,  # type: ignore[arg-type]
            cursor=cursor,
            limit=limit,
        )
    except InvalidCursorError as exc:
        raise service_exception_to_http(exc) from exc


@router.get("/{application_id}", response_model=CandidateApplicationDetail)
async def get_application(
    application_id: int,
    current: tuple[User, CandidateProfile] = Depends(get_current_candidate),
    session: AsyncSession = Depends(get_session),
) -> CandidateApplicationDetail:
    """Single application detail — 404 if foreign or WITHDRAWN."""
    _, profile = current
    try:
        return await get_my_application(
            session,
            candidate_id=profile.id,  # type: ignore[arg-type]
            application_id=application_id,
        )
    except ApplicationNotFoundError as exc:
        raise service_exception_to_http(exc) from exc


@router.patch("/{application_id}", response_model=CandidateApplicationDetail)
async def edit_application(
    application_id: int,
    service_concept: str | None = Form(None, max_length=2000),
    salary_expectations: str | None = Form(None, max_length=2000),
    strength: str | None = Form(None, max_length=2000),
    growth_area: str | None = Form(None, max_length=2000),
    resume: UploadFile | None = File(None),
    current: tuple[User, CandidateProfile] = Depends(get_current_candidate),
    session: AsyncSession = Depends(get_session),
) -> CandidateApplicationDetail:
    """Partially update text answers and/or replace the resume snapshot.

    Only allowed when ``status == NEW``. Returns the updated detail.
    """
    if (
        all(
            f is None
            for f in (service_concept, salary_expectations, strength, growth_area)
        )
        and resume is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="empty_body"
        )

    resume_bytes = (
        await validate_upload(resume, _RESUME_ALLOWED_TYPES, _RESUME_MAX_BYTES)
        if resume
        else None
    )
    resume_filename = resume.filename if resume else None

    _, profile = current
    try:
        return await edit_my_application(
            session,
            candidate_id=profile.id,  # type: ignore[arg-type]
            application_id=application_id,
            data=ApplicationEditData(
                service_concept=service_concept,
                salary_expectations=salary_expectations,
                strength=strength,
                growth_area=growth_area,
                resume_bytes=resume_bytes,
                resume_filename=resume_filename,
            ),
            storage=get_storage_provider(),
        )
    except ApplicationNotFoundError as exc:
        raise service_exception_to_http(exc) from exc
    except ApplicationNotEditableError as exc:
        raise service_exception_to_http(exc) from exc
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_resume"
        )


@router.post("/{application_id}/withdraw", status_code=204)
async def withdraw_application(
    application_id: int,
    current: tuple[User, CandidateProfile] = Depends(get_current_candidate),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Withdraw the application — only allowed when ``status == NEW``."""
    _, profile = current
    try:
        await withdraw_my_application(
            session,
            candidate_id=profile.id,  # type: ignore[arg-type]
            application_id=application_id,
        )
    except ApplicationNotFoundError as exc:
        raise service_exception_to_http(exc) from exc
    except ApplicationNotEditableError as exc:
        raise service_exception_to_http(exc) from exc
    return Response(status_code=204)


@router.get("/{application_id}/resume")
async def download_application_resume(
    application_id: int,
    current: tuple[User, CandidateProfile] = Depends(get_current_candidate),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Stream the snapshotted resume tied to this application.

    Collapses foreign-id, WITHDRAWN, and no-snapshot into the same 404 so the
    endpoint can't be used to probe ownership separately from existence.
    """
    _, profile = current
    try:
        storage_key = await get_application_resume_key(
            session,
            candidate_id=profile.id,  # type: ignore[arg-type]
            application_id=application_id,
        )
    except ApplicationNotFoundError as exc:
        raise service_exception_to_http(exc) from exc
    return await stream_resume(basename_from_storage_key(storage_key))
