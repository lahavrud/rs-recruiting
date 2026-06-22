"""Shared handler for the public apply endpoints.

Both ``POST /api/candidates/apply`` and ``POST /api/jobs/{job_id}/apply``
collapse into the same logic: collect the form fields, dispatch the
optional claim/logged-in branches, and map domain exceptions to the
structured 409 shapes documented in ``docs/API_DESIGN.md``.

Carved out of ``applications.py`` to keep that router file under the
200-line API cap. HTTPException stays here (router-layer concern); the
service-layer code in ``src/services/public/applications.py`` raises
domain exceptions only.
"""

from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.dependencies import client_ip
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.transactions import transactional
from src.core.services.file_validation import validate_upload
from src.enums import UserRole
from src.models import User
from src.schemas import CandidateProfileCreate, CandidateProfileRead
from src.schemas.auth import _validate_password_complexity
from src.services.exceptions import (
    ApplicationAlreadyEditableError,
    ApplicationAlreadyExistsError,
    ApplicationAlreadyLockedError,
    EmailAlreadyExistsError,
    JobNotFoundError,
)
from src.services.public.applications import (
    create_candidate_profile,
    get_candidate_profile,
)

_RESUME_ALLOWED_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)
_RESUME_MAX_BYTES = 10 * 1024 * 1024


def validate_optional_password(
    password: str | None, password_confirm: str | None
) -> None:
    """Claim path: enforce the registration password rules on the
    multipart form fields since there's no Pydantic schema on this surface."""
    if password is None:
        return
    if password != password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="passwords_do_not_match",
        )
    try:
        _validate_password_complexity(password)
    except ValueError as e:
        # Opaque code instead of str(e) — the validator message included
        # specifics about which rule failed.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="password_complexity_failed",
        ) from e


async def apply_to_job(
    job_id: int,
    full_name: str,
    email: str,
    phone: str,
    linkedin_url: str | None,
    service_concept: str | None,
    salary_expectations: str | None,
    growth_area: str | None,
    strength: str | None,
    privacy_accepted: bool,
    terms_accepted: bool,
    resume: UploadFile | None,
    password: str | None,
    password_confirm: str | None,
    request: Request,
    session: AsyncSession,
    current_user: User | None,
) -> CandidateProfileRead:
    """Dispatched apply: anonymous / anonymous-claim / logged-in candidate."""
    # Anonymous: both consent checkboxes are required. Logged-in candidates
    # already accepted at activation time.
    if current_user is None:
        if not privacy_accepted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="privacy_consent_required",
            )
        if not terms_accepted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="terms_consent_required",
            )

    if current_user is not None and current_user.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only_candidates_can_apply",
        )

    # Claim is meaningful only on the anonymous path.
    effective_password = password if current_user is None else None
    if effective_password is not None:
        validate_optional_password(effective_password, password_confirm)

    resume_file: bytes | None = None
    resume_filename: str | None = None
    if resume is not None:
        resume_file = await validate_upload(
            resume, _RESUME_ALLOWED_TYPES, _RESUME_MAX_BYTES
        )
        resume_filename = resume.filename

    # Every live application requires a resume. Logged-in candidates that
    # didn't upload a new file fall back to the snapshot already on their
    # profile (no re-upload). Anonymous applicants who omit the field
    # are rejected with a structured 422.
    fallback_resume_path: str | None = None
    fallback_resume_filename: str | None = None
    fallback_resume_hash: str | None = None
    if resume_file is None and current_user is not None:
        existing_profile = await get_candidate_profile(current_user.id, session)
        if existing_profile and existing_profile.resume_path:
            fallback_resume_path = existing_profile.resume_path
            fallback_resume_filename = existing_profile.resume_filename
            fallback_resume_hash = existing_profile.resume_hash
    if resume_file is None and fallback_resume_path is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="resume_required",
        )

    candidate_data = CandidateProfileCreate(
        full_name=full_name,
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
    )

    try:
        async with transactional(session):
            candidate = await create_candidate_profile(
                candidate_data=candidate_data,
                job_id=job_id,
                resume_file=resume_file,
                resume_filename=resume_filename,
                fallback_resume_path=fallback_resume_path,
                fallback_resume_filename=fallback_resume_filename,
                fallback_resume_hash=fallback_resume_hash,
                session=session,
                consent_ip=client_ip(request),
                consent_ua=request.headers.get("user-agent"),
                service_concept=service_concept,
                salary_expectations=salary_expectations,
                strength=strength,
                growth_area=growth_area,
                candidate_user=current_user,
                claim_password=effective_password,
            )
        return candidate
    except ApplicationAlreadyEditableError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "already_applied_editable",
                "application_id": e.application_id,
            },
        ) from e
    except ApplicationAlreadyLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "already_applied_locked"},
        ) from e
    except EmailAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "email_already_registered"},
        ) from e
    except (JobNotFoundError, ApplicationAlreadyExistsError) as e:
        raise service_exception_to_http(e) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid_application",
        ) from e
