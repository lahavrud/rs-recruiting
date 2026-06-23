"""Helpers for the public apply-to-job flow.

Carved out of ``applications.py`` to keep the main module under the
``src/services`` 300-line cap. Four responsibilities live here:

* ``validate_and_upload_resume`` — magic-byte + size + extension checks
  followed by a storage upload, returning the storage key.
* ``check_no_blocking_application`` — duplicate-apply pre-check, raising
  the editable / locked variants.
* ``upsert_candidate_and_application`` — the find-or-create profile +
  Application row pair, with consent-write and resume-snapshot semantics.
* ``send_application_emails`` — the candidate-confirmation + admin-
  notification fan-out, normally invoked via ``defer_after_commit``.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.services.file_validation import is_valid_document_magic_bytes
from src.core.services.storage import StorageProvider
from src.core.tasks import enqueue_email_task
from src.enums import ApplicationStatus, UserRole
from src.models import Application, CandidateProfile, Job, User
from src.schemas import CandidateProfileCreate
from src.services.admin.companies import get_all_admin_emails
from src.services.company.candidates import (
    find_candidate_by_email,
    update_candidate_profile,
)
from src.services.exceptions import (
    ApplicationAlreadyEditableError,
    ApplicationAlreadyLockedError,
    EmailAlreadyExistsError,
)
from src.services.utils.legal import (
    CURRENT_PRIVACY_POLICY_VERSION,
    CURRENT_TERMS_OF_SERVICE_VERSION,
)
from src.templates.email import (
    build_application_received_html,
    build_new_application_admin_html,
)

_ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
_MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10 MB
_MIME_BY_EXT = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
}


async def validate_and_upload_resume(
    resume_file: bytes,
    resume_filename: str,
    storage: StorageProvider,
) -> tuple[str, str]:
    """Validate resume file (type, size, magic bytes) and upload it.

    Returns ``(storage_key, sha256_hex)``. Raises ``ValueError`` on any
    validation failure so callers can map the error consistently.
    """
    ext = resume_filename.lower().rsplit(".", 1)[-1] if "." in resume_filename else ""
    if f".{ext}" not in _ALLOWED_EXTENSIONS:
        raise ValueError(f"Invalid file type. Allowed: PDF, DOC, DOCX. Got: {ext}")
    if len(resume_file) > _MAX_RESUME_BYTES:
        raise ValueError(
            f"File size exceeds maximum of 10MB. Got: {len(resume_file)} bytes"
        )
    if not is_valid_document_magic_bytes(resume_file, ext):
        raise ValueError("Resume file content does not match the declared file type")

    content_type = _MIME_BY_EXT.get(ext, "application/octet-stream")
    storage_key = await storage.upload_file(
        file_content=resume_file,
        file_name=f"resumes/{resume_filename}",
        content_type=content_type,
    )
    return storage_key, hashlib.sha256(resume_file).hexdigest()


async def check_no_blocking_application(
    session: AsyncSession, job_id: int, candidate_id: int
) -> None:
    """Reject re-apply when a non-WITHDRAWN application already exists."""
    result = await session.execute(
        select(Application).where(  # pyright: ignore[reportArgumentType]
            Application.job_id == job_id,
            Application.candidate_id == candidate_id,
            Application.status != ApplicationStatus.WITHDRAWN,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return
    if existing.status == ApplicationStatus.NEW:
        assert existing.id is not None
        raise ApplicationAlreadyEditableError(application_id=existing.id)
    raise ApplicationAlreadyLockedError(
        f"Application {existing.id} is no longer editable"
    )


@dataclass
class CandidateApplicationPayload:
    """Consent metadata + resume snapshot fields for an apply submission.

    Grouped separately from `session`/`candidate_data`/`job_id` (the "what
    and where" of the upsert) since these fields are either consent-write
    inputs (timestamp is derived internally, but IP/UA + skip-flag travel
    together) or the per-Application resume snapshot, plus the optional
    authenticated user that toggles the skip-consent-write behavior.
    """

    resume_path: str | None = None
    consent_ip: str | None = None
    consent_ua: str | None = None
    service_concept: str | None = None
    salary_expectations: str | None = None
    strength: str | None = None
    growth_area: str | None = None
    skip_consent_write: bool = False
    candidate_user: User | None = None
    resume_filename: str | None = None
    resume_hash: str | None = None


async def upsert_candidate_and_application(
    session: AsyncSession,
    candidate_data: CandidateProfileCreate,
    job_id: int,
    payload: CandidateApplicationPayload,
) -> CandidateProfile:
    """Find-or-create the candidate profile and create the Application row.

    Order matters: pre-checks fire before any profile mutation so a 409
    doesn't leave the profile half-updated with the new request's values.
    """
    if payload.candidate_user is None:
        user_result = await session.execute(
            select(User).where(User.email == candidate_data.email)  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
        )
        matching_user = user_result.scalar_one_or_none()
        if (
            matching_user is not None
            and matching_user.is_active
            and matching_user.role == UserRole.CANDIDATE
        ):
            raise EmailAlreadyExistsError(candidate_data.email)

    now = datetime.now(timezone.utc)
    existing = await find_candidate_by_email(
        email=candidate_data.email, session=session
    )
    if existing and existing.id is not None:
        await check_no_blocking_application(session, job_id, existing.id)

        candidate = await update_candidate_profile(
            candidate=existing,
            candidate_data=candidate_data,
            resume_path=payload.resume_path,
            resume_filename=payload.resume_filename,
            resume_hash=payload.resume_hash,
            session=session,
        )
        if not payload.skip_consent_write:
            candidate.consent_given_at = now
            candidate.consent_policy_version = CURRENT_PRIVACY_POLICY_VERSION
            candidate.consent_ip = payload.consent_ip
            candidate.consent_user_agent = payload.consent_ua
            candidate.tos_accepted_at = now
            candidate.tos_version = CURRENT_TERMS_OF_SERVICE_VERSION
        await session.flush()
    else:
        candidate = CandidateProfile(
            full_name=candidate_data.full_name,
            email=candidate_data.email,
            phone=candidate_data.phone,
            resume_path=payload.resume_path,
            resume_filename=payload.resume_filename,
            resume_hash=payload.resume_hash,
            linkedin_url=candidate_data.linkedin_url,
            consent_given_at=None if payload.skip_consent_write else now,
            consent_policy_version=(
                None if payload.skip_consent_write else CURRENT_PRIVACY_POLICY_VERSION
            ),
            consent_ip=None if payload.skip_consent_write else payload.consent_ip,
            consent_user_agent=(
                None if payload.skip_consent_write else payload.consent_ua
            ),
            tos_accepted_at=None if payload.skip_consent_write else now,
            tos_version=(
                None if payload.skip_consent_write else CURRENT_TERMS_OF_SERVICE_VERSION
            ),
        )
        session.add(candidate)
        await session.flush()

    # Resume snapshot per Application — independent of profile's "latest"
    # resume; fixes a missing snapshot write that previously let a
    # candidate's profile resume change retroactively for past applications.
    session.add(
        Application(
            job_id=job_id,
            candidate_id=candidate.id,  # type: ignore[arg-type]  # model id is int | None pre-flush; always set once persisted
            status=ApplicationStatus.NEW,
            service_concept=payload.service_concept,
            salary_expectations=payload.salary_expectations,
            strength=payload.strength,
            growth_area=payload.growth_area,
            resume_path=payload.resume_path,
            resume_filename=payload.resume_filename,
            resume_hash=payload.resume_hash,
        )
    )
    return candidate


async def send_application_emails(
    candidate: CandidateProfile,
    job: Job,
    company_name: str,
    session: AsyncSession,
) -> None:
    """Enqueue confirmation email to the candidate and notification to admins."""
    await enqueue_email_task(
        to=candidate.email,
        subject=f"מועמדותך למשרת '{job.title}' התקבלה",
        body=(
            f"שלום {candidate.full_name},\n\n"
            f"קיבלנו את מועמדותך למשרת '{job.title}'. צוות RS Recruiting "
            "יבחן את הפרטים בקרוב ויחזור אליך עם עדכון."
        ),
        html_body=build_application_received_html(
            candidate_name=candidate.full_name,
            job_title=job.title,
        ),
    )

    if settings.admin_notification_email:
        admin_recipients: list[str] | str = settings.admin_notification_email
    else:
        admin_recipients = await get_all_admin_emails(session)

    if admin_recipients:
        admin_url = f"{settings.frontend_base_url}/login?redirect=/admin/applications"
        await enqueue_email_task(
            to=admin_recipients,
            subject=f"מועמדות חדשה למשרת '{job.title}' — {candidate.full_name}",
            body=(
                f"מועמדות חדשה התקבלה:\n\n"
                f"שם: {candidate.full_name}\n"
                f'דוא"ל: {candidate.email}\n'
                f"טלפון: {candidate.phone or 'לא צויין'}\n"
                f"משרה: {job.title}\n"
                f"חברה: {company_name}\n\n"
                f"מעבר לניהול: {admin_url}"
            ),
            html_body=build_new_application_admin_html(
                candidate_name=candidate.full_name,
                candidate_email=candidate.email,
                candidate_phone=candidate.phone,
                candidate_linkedin=candidate.linkedin_url,
                job_title=job.title,
                company_name=company_name,
                admin_url=admin_url,
            ),
        )
