"""Application service layer: the public apply-to-job flow.

Separate from `candidates.py` (profile lookup + update primitives) so
that the heavyweight create-application code path — file validation,
storage upload, upsert, and email side effects — lives in a focused
module.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.transactions import defer_after_commit
from src.core.services.storage import get_storage_provider

# Re-export so existing tests that `@patch("src.services.public.applications.
# enqueue_email_task")` continue to work even though the email enqueue happens
# in `_application_helpers`. See `tests/conftest.py::_EMAIL_TASK_TARGETS`.
from src.core.tasks import enqueue_email_task  # noqa: F401
from src.enums import JobStatus
from src.models import CandidateProfile, Job, User
from src.schemas import CandidateProfileCreate, CandidateProfileRead
from src.services.exceptions import EmailAlreadyExistsError, JobNotFoundError
from src.services.public._application_helpers import (
    send_application_emails,
    upsert_candidate_and_application,
    validate_and_upload_resume,
)
from src.services.utils.audit import record_audit_event
from src.services.utils.legal import (
    CURRENT_PRIVACY_POLICY_VERSION,
    CURRENT_TERMS_OF_SERVICE_VERSION,
)


async def create_candidate_profile(
    candidate_data: CandidateProfileCreate,
    job_id: int,
    resume_file: bytes | None = None,
    resume_filename: str | None = None,
    fallback_resume_path: str | None = None,
    fallback_resume_filename: str | None = None,
    fallback_resume_hash: str | None = None,
    session: AsyncSession | None = None,
    consent_ip: str | None = None,
    consent_ua: str | None = None,
    service_concept: str | None = None,
    salary_expectations: str | None = None,
    strength: str | None = None,
    growth_area: str | None = None,
    *,
    candidate_user: User | None = None,
    claim_password: str | None = None,
) -> CandidateProfileRead:
    """Create a candidate profile and application for a job.

    Three flavors, dispatched by the (``candidate_user``, ``claim_password``)
    combo:

    * Anonymous apply (no user, no password) — existing behavior.
    * Anonymous claim (no user, password supplied) — submit the application
      AND register a candidate User in the same request. Activation token is
      minted and emailed via the shared registration helper. If the email is
      already taken by an active candidate user the apply is rejected
      upfront with ``EmailAlreadyExistsError`` and the password is irrelevant.
    * Logged-in candidate apply (user supplied) — use ``user.email`` instead
      of the form's email, snapshot the new resume on the Application,
      sync any updated identity fields onto the candidate's existing
      profile, and skip per-application consent writes (consent was already
      captured at activation time).

    Raises:
        ValueError: If session is missing or file upload fails.
        JobNotFoundError: If the job does not exist.
        EmailAlreadyExistsError: If apply email belongs to an active
            candidate user.
        ApplicationAlreadyEditableError / ApplicationAlreadyLockedError: per
            ``check_no_blocking_application``.
    """
    if session is None:
        raise ValueError("Database session is required")

    # Restrict apply to PUBLISHED jobs only — PENDING_APPROVAL / CLOSED /
    # REJECTED rows are not visible on the public job board but a candidate
    # who has a stale link, brute-forces sequential IDs, or replays an old
    # URL must not be able to slip an application past them.
    # Pending / closed / rejected rows behave identically to "not found"
    # from the public surface; we collapse them all into JobNotFoundError
    # so the response is opaque about why the apply was rejected.
    job_row = await session.execute(
        select(Job)
        .options(selectinload(Job.company))
        .where(
            Job.id == job_id,  # pyright: ignore[reportArgumentType]
            Job.status == JobStatus.PUBLISHED,
        )
    )
    job = job_row.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job with ID {job_id} not found or not published")

    company_name = job.company.name if job.company else "Unknown Company"

    # Logged-in candidates ignore the form's email field (it could mismatch
    # their session email and would let one user spoof another's submission).
    if candidate_user is not None:
        candidate_data = candidate_data.model_copy(
            update={"email": candidate_user.email}
        )

    resume_path: str | None = None
    resume_hash: str | None = None
    if resume_file is not None and resume_filename is not None:
        try:
            resume_path, resume_hash = await validate_and_upload_resume(
                resume_file, resume_filename, get_storage_provider()
            )
        except Exception as e:
            raise ValueError(f"Failed to upload resume file: {e}") from e
    elif fallback_resume_path is not None:
        # No new upload — reuse the candidate's existing profile resume
        # snapshot. The file is already in storage, no upload needed.
        # The Application row gets this path as its own snapshot so future
        # profile-resume replacements don't retroactively change history.
        resume_path = fallback_resume_path
        resume_filename = fallback_resume_filename
        resume_hash = fallback_resume_hash

    candidate = await upsert_candidate_and_application(
        session,
        candidate_data,
        job_id,
        resume_path,
        consent_ip,
        consent_ua,
        service_concept=service_concept,
        salary_expectations=salary_expectations,
        strength=strength,
        growth_area=growth_area,
        # Logged-in flow already has consent on the profile — don't overwrite
        # the activation-time IP/UA with the current (possibly different
        # device's) values.
        skip_consent_write=candidate_user is not None,
        candidate_user=candidate_user,
        resume_filename=resume_filename,
        resume_hash=resume_hash,
    )

    # Logged-in candidate → ensure the profile is linked to their User row
    # (defensive; activation should have done this already).
    if candidate_user is not None and candidate.user_id is None:
        candidate.user_id = candidate_user.id

    await session.flush()
    await session.refresh(candidate)

    # Audit only the per-application consent capture path — claim/logged-in
    # flows have their own audit (candidate_register_via_apply / activation).
    if candidate_user is None:
        await record_audit_event(
            session,
            actor_user_id=None,
            action="candidate.consent",
            target_type="CandidateProfile",
            target_id=candidate.id,  # type: ignore[arg-type]  # model id is int | None pre-flush; always set once persisted
            detail=f"policy_version={CURRENT_PRIVACY_POLICY_VERSION}",
            ip_address=consent_ip,
        )
        await record_audit_event(
            session,
            actor_user_id=None,
            action="candidate.terms_accept",
            target_type="CandidateProfile",
            target_id=candidate.id,  # type: ignore[arg-type]  # model id is int | None pre-flush; always set once persisted
            detail=f"terms_version={CURRENT_TERMS_OF_SERVICE_VERSION}",
            ip_address=consent_ip,
        )

    # Anonymous claim: mint a candidate User + activation token using the
    # shared registration helper. The User starts is_active=False; the
    # candidate's CandidateProfile.user_id stays NULL until activation links
    # them. If the email belongs to an already-pending user the helper
    # updates the password + replaces the token (re-registration semantics).
    if candidate_user is None and claim_password is not None:
        # Lazy import to avoid a circular dep at module load (auth →
        # public → auth).
        from src.services.auth.candidate_registration import register_candidate

        try:
            await register_candidate(
                candidate_data.email,
                claim_password,
                candidate_data.full_name,
                privacy_accepted=True,
                terms_accepted=True,
                session=session,
                ip_address=consent_ip,
                user_agent=consent_ua,
            )
            await record_audit_event(
                session,
                actor_user_id=None,
                action="candidate_register_via_apply",
                target_type="CandidateProfile",
                target_id=candidate.id,  # type: ignore[arg-type]  # model id is int | None pre-flush; always set once persisted
                ip_address=consent_ip,
            )
        except EmailAlreadyExistsError:
            # Race: a registration landed between our pre-check and here.
            # Surface to the caller so the apply also fails cleanly.
            raise

    _candidate_snapshot = candidate
    _job_snapshot = job
    _company_name_snapshot = company_name
    defer_after_commit(
        lambda: send_application_emails(
            _candidate_snapshot, _job_snapshot, _company_name_snapshot, session
        )
    )
    return CandidateProfileRead.model_validate(candidate)


async def get_candidate_profile(
    user_id: int, session: AsyncSession
) -> CandidateProfile | None:
    """Look up the CandidateProfile linked to a given user, or None."""
    result = await session.execute(
        select(CandidateProfile).where(
            CandidateProfile.user_id == user_id  # type: ignore[arg-type]
        )
    )
    return result.scalar_one_or_none()
