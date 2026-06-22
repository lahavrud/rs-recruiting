"""Authenticated candidate self-service profile endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_candidate
from src.core.infrastructure.transactions import transactional
from src.core.services.file_validation import validate_upload
from src.core.services.storage import get_storage_provider
from src.models import CandidateProfile, User
from src.schemas import CandidateMeRead, CandidateMeUpdate
from src.services.candidate.profile import (
    apply_identity_patch,
    remove_resume,
    replace_resume,
)

_RESUME_ALLOWED_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)
_RESUME_MAX_BYTES = 10 * 1024 * 1024

router = APIRouter(prefix="/api/candidate", tags=["candidate"])


def _to_me_read(user: User, profile: CandidateProfile) -> CandidateMeRead:
    """Project the User + CandidateProfile pair into the /me response shape."""
    return CandidateMeRead(
        id=profile.id,  # type: ignore[arg-type]  # model id is int | None pre-flush; always set once persisted
        email=user.email,
        full_name=profile.full_name,
        phone=profile.phone,
        linkedin_url=profile.linkedin_url,
        resume_path=profile.resume_path,
        resume_filename=profile.resume_filename,
        consent_given_at=profile.consent_given_at,
        consent_policy_version=profile.consent_policy_version,
        created_at=profile.created_at,
    )


@router.get("/me", response_model=CandidateMeRead)
async def get_me(
    current: tuple[User, CandidateProfile] = Depends(get_current_candidate),
) -> CandidateMeRead:
    """Return the authenticated candidate's own profile (identity + consent)."""
    user, profile = current
    return _to_me_read(user, profile)


@router.patch("/me", response_model=CandidateMeRead)
async def patch_me(
    body: dict[str, Any],
    current: tuple[User, CandidateProfile] = Depends(get_current_candidate),
    session: AsyncSession = Depends(get_session),
) -> CandidateMeRead:
    """Patch full_name / phone / linkedin_url.

    Email is intentionally NOT editable — the schema rejects ``email`` via
    ``extra="forbid"`` rather than silently dropping it, so a client trying
    to change it gets a clear 400.
    """
    if "email" in body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email_not_editable",
        )
    try:
        patch = CandidateMeUpdate.model_validate(body)
    except PydanticValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            # Stringify each error: Pydantic's raw errors() can contain
            # non-JSON-serializable values (URL objects, etc.) that crash
            # FastAPI's response serialization.
            detail=[str(e) for e in exc.errors()],
        ) from exc

    user, profile = current
    try:
        async with transactional(session):
            await apply_identity_patch(profile, patch, session)
    except ValueError as e:
        # Extension-lock on resume_filename rename + the "rename without
        # a stored resume" guard both raise here.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    return _to_me_read(user, profile)


@router.post("/me/resume", response_model=CandidateMeRead)
async def upload_resume(
    resume: UploadFile = File(...),
    current: tuple[User, CandidateProfile] = Depends(get_current_candidate),
    session: AsyncSession = Depends(get_session),
) -> CandidateMeRead:
    """Upload (or replace) the candidate's profile-level resume."""
    content = await validate_upload(resume, _RESUME_ALLOWED_TYPES, _RESUME_MAX_BYTES)
    filename = resume.filename or "resume"
    user, profile = current
    try:
        async with transactional(session):
            await replace_resume(
                profile,
                content,
                filename,
                resume.content_type,
                get_storage_provider(),
                session,
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid_resume",
        ) from e
    return _to_me_read(user, profile)


@router.delete("/me/resume", response_model=CandidateMeRead)
async def delete_resume(
    current: tuple[User, CandidateProfile] = Depends(get_current_candidate),
    session: AsyncSession = Depends(get_session),
) -> CandidateMeRead:
    """Idempotent resume removal."""
    user, profile = current
    async with transactional(session):
        await remove_resume(profile, get_storage_provider(), session)
    return _to_me_read(user, profile)
