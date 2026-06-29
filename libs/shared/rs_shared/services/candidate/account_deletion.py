"""Candidate GDPR account deletion.

Two-step flow:

1. ``request_account_deletion(email, session, ...)`` — finds the candidate
   profile by email, rate-limits (3 requests per 24h per profile), mints an
   ``AccountDeletionToken``, and defers a confirmation email.  Always returns
   silently (email-enumeration protection).

2. ``confirm_deletion(raw_token, session, storage)`` — atomically tombstones
   the candidate: NULLs PII fields, sets ``deleted_at``, scrubs application
   resume snapshots, best-effort deletes the resume from storage, then
   hard-deletes the linked ``User`` row (FK CASCADE cleans up sessions/tokens;
   FK SET NULL clears ``CandidateProfile.user_id``).
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.infrastructure.security import hash_token
from rs_shared.core.infrastructure.transactions import defer_after_commit
from rs_shared.core.services.storage import StorageProvider
from rs_shared.core.tasks import enqueue_email_task
from rs_shared.models import AccountDeletionToken, Application, CandidateProfile, User
from rs_shared.services.exceptions import InvalidAccountDeletionTokenError
from rs_shared.services.utils.audit import record_audit_event
from rs_shared.templates.email import build_account_deletion_confirmation_html

logger = logging.getLogger(__name__)

_TOKEN_TTL = timedelta(hours=24)


def _scrub_candidate_pii(profile: CandidateProfile) -> None:
    """NULL all PII fields on a CandidateProfile and set deleted_at.

    Called by both the self-service and admin tombstone paths so that
    adding a new PII field only requires a single-location change here.
    """
    profile.deleted_at = datetime.now(timezone.utc)
    profile.full_name = "[מחוק]"
    profile.email = f"deleted-{profile.id}@deleted"
    profile.phone = None
    profile.resume_path = None
    profile.resume_filename = None
    profile.resume_hash = None
    profile.parsed_text = None
    profile.resume_summary = None
    profile.embedding = None
    profile.linkedin_url = None
    profile.consent_ip = None
    profile.consent_user_agent = None


_RATE_LIMIT_WINDOW = timedelta(hours=24)
_RATE_LIMIT_MAX = 3


async def _rate_limit_ok(profile_id: int, session: AsyncSession) -> bool:
    window_start = datetime.now(timezone.utc) - _RATE_LIMIT_WINDOW
    result = await session.execute(
        select(func.count())
        .select_from(AccountDeletionToken)
        .where(
            AccountDeletionToken.candidate_profile_id == profile_id,  # type: ignore[arg-type]
            AccountDeletionToken.created_at > window_start,
        )
    )
    return result.scalar_one() < _RATE_LIMIT_MAX


async def request_account_deletion(
    email: str,
    session: AsyncSession,
    *,
    ip_address: str | None = None,
) -> None:
    """Initiate account deletion for the candidate identified by *email*.

    Silent on unknown emails and already-deleted profiles (email-enumeration
    and idempotency). The caller always observes the same 202 response.
    """
    cleaned = email.lower().strip()
    if not cleaned:
        return

    result = await session.execute(
        select(CandidateProfile).where(
            CandidateProfile.email == cleaned  # pyright: ignore[reportArgumentType]
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None or profile.id is None or profile.deleted_at is not None:
        return

    if not await _rate_limit_ok(profile.id, session):
        logger.info(
            "account_deletion_request_rate_limited",
            extra={"profile_id": profile.id},
        )
        return

    raw_token = secrets.token_urlsafe(32)
    token_record = AccountDeletionToken(
        token_hash=hash_token(raw_token),
        candidate_profile_id=profile.id,
        expires_at=datetime.now(timezone.utc) + _TOKEN_TTL,
        used=False,
    )
    session.add(token_record)

    await record_audit_event(
        session,
        actor_user_id=profile.user_id,
        action="account_deletion_requested",
        target_type="candidateprofile",
        target_id=profile.id,
        ip_address=ip_address,
    )

    confirm_url = (
        f"{settings.frontend_base_url}/candidate/delete-account?token={raw_token}"
    )
    recipient = profile.email
    html = build_account_deletion_confirmation_html(confirm_url=confirm_url)
    plain = (
        "קיבלנו בקשה למחיקת חשבונכם ב-RS Recruiting.\n"
        f"לאישור המחיקה לחצו על הקישור (תקף ל-24 שעות):\n{confirm_url}\n\n"
        "אם לא ביקשתם למחוק את החשבון — התעלמו מהמייל הזה."
    )
    defer_after_commit(
        lambda: enqueue_email_task(
            to=recipient,
            subject="אישור מחיקת חשבון — RS Recruiting",
            body=plain,
            html_body=html,
        )
    )


async def _load_active_deletion_token(
    raw_token: str, session: AsyncSession
) -> AccountDeletionToken:
    """Load a deletion token only if it is still usable (not used, not expired)."""
    result = await session.execute(
        select(AccountDeletionToken)
        .where(
            AccountDeletionToken.token_hash  # pyright: ignore[reportArgumentType]
            == hash_token(raw_token)
        )
        .with_for_update()
    )
    record = result.scalar_one_or_none()
    if record is None or record.used:
        logger.warning(
            "account_deletion_token_invalid", extra={"reason": "not_found_or_used"}
        )
        raise InvalidAccountDeletionTokenError()
    if record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        logger.warning("account_deletion_token_invalid", extra={"reason": "expired"})
        raise InvalidAccountDeletionTokenError()
    return record


async def check_deletion_token(raw_token: str, session: AsyncSession) -> None:
    """Validate a deletion token without consuming it.

    Raises ``InvalidAccountDeletionTokenError`` if invalid, expired, or used.
    Used by the frontend to gate the confirmation page on a usable link.
    """
    await _load_active_deletion_token(raw_token, session)


async def confirm_deletion(
    raw_token: str,
    session: AsyncSession,
    *,
    storage: StorageProvider,
) -> None:
    """Atomically tombstone the candidate identified by *raw_token*.

    Steps (all within one transaction):
    1. Validate and consume the deletion token.
    2. NULL ``Application.resume_path`` for all candidate applications.
    3. Best-effort: delete the candidate's resume file from storage.
    4. Scrub all PII fields on ``CandidateProfile``; set ``deleted_at``.
    5. Hard-delete the linked ``User`` row (FK CASCADE sweeps sessions/tokens;
       FK SET NULL clears ``CandidateProfile.user_id``).
    6. Write an ``account_deleted`` audit event.

    Raises ``InvalidAccountDeletionTokenError`` if the token is unusable.
    """
    token = await _load_active_deletion_token(raw_token, session)
    token.used = True

    profile = await session.get(CandidateProfile, token.candidate_profile_id)
    if profile is None:
        # FK CASCADE should have removed the token too; treat as success.
        return

    if profile.deleted_at is not None:
        # Admin already tombstoned this profile — acknowledge without re-running.
        logger.info(
            "account_deletion_confirm_noop_already_tombstoned",
            extra={"profile_id": profile.id},
        )
        return

    # NULL application resume snapshots (preserve application rows themselves).
    await session.execute(
        update(Application)
        .where(Application.candidate_id == profile.id)  # pyright: ignore[reportArgumentType]
        .values(resume_path=None, resume_filename=None, resume_hash=None)
    )

    # Best-effort resume storage delete — must not abort the deletion on failure.
    if profile.resume_path:
        try:
            await storage.delete_file(profile.resume_path)
        except Exception:
            logger.warning(
                "account_deletion_resume_storage_error",
                extra={"profile_id": profile.id},
            )

    actor_user_id = profile.user_id

    # Tombstone: scrub all PII, mark the row as deleted.
    _scrub_candidate_pii(profile)

    # Hard-delete the linked User.  FK SET NULL cascade sets profile.user_id to
    # NULL automatically; FK CASCADE cleans up RefreshToken, PasswordResetToken,
    # ActivationToken, DataExportRequest rows.
    if actor_user_id is not None:
        user = await session.get(User, actor_user_id)
        if user is not None:
            await session.delete(user)
            await session.flush()

    await record_audit_event(
        session,
        actor_user_id=None,  # user row is gone at this point
        action="account_deleted",
        target_type="candidateprofile",
        target_id=profile.id,
    )

    logger.info("account_deleted", extra={"profile_id": profile.id})
