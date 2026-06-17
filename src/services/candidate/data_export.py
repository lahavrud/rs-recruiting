"""Candidate GDPR data export (Sprint 11 / #608).

Flow:

1. ``POST /api/candidate/me/export`` enqueues ``build_data_export_task``
   and returns 202. Rate limit: at most one *unused* ``DataExportRequest``
   per user in the last 24 hours — enforced by counting DB rows rather
   than touching Redis (the row IS the rate limit; one less moving
   piece).
2. The Arq task assembles a ZIP containing ``data.json`` (profile +
   applications + non-PII audit slice) and per-application resume
   binaries fetched from storage. Uploads the ZIP to storage with a
   ``exports/{user_id}/{uuid}.zip`` key, mints a ``DataExportRequest``
   carrying a hashed download token, and emails the candidate a signed
   download link.
3. ``GET /api/candidate/me/export/{token}`` looks the token up by hash,
   verifies it's unused + unexpired, streams the ZIP, and marks
   ``used=True``.

Cleanup of expired / used rows + the underlying ZIP objects lands in
issue #10's nightly cron. Until then, the rows pile up; storage costs
are bounded by the per-user 24h rate limit.
"""

from __future__ import annotations

import io
import json
import logging
import secrets
import zipfile
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.security import hash_token
from src.core.services.storage import StorageProvider
from src.models import Application, AuditLog, CandidateProfile, DataExportRequest, User

logger = logging.getLogger(__name__)

# 24h TTL on the signed download link.
DATA_EXPORT_TTL_HOURS = 24

# Audit actions the candidate is allowed to see in their own export. We pick
# from the set of actions whose ``actor_user_id`` would be the candidate
# themselves. Deletion-related actions (#611) are listed here pre-emptively;
# they're harmless when they don't exist yet (the SELECT just returns 0
# rows for them).
CANDIDATE_VISIBLE_AUDIT_ACTIONS = (
    "candidate_register_requested",
    "candidate_resend_activation_requested",
    "candidate_activated",
    "candidate_register_via_apply",
    "password_changed",
    "password_reset",
    "account_deletion_requested",
    "account_deleted",
)


async def _gather_candidate_data(
    user_id: int,
    session: AsyncSession,
) -> tuple[User, CandidateProfile | None, list[Application], list[AuditLog]]:
    """One pass to read everything the export touches.

    Returns ``(user, profile, applications, audit_entries)``. The profile may
    be ``None`` if the candidate hasn't activated yet — defensive; the
    endpoint should reject pre-activation users earlier, but the task is
    callable from a worker so it shouldn't crash on that path.
    """
    user_row = await session.execute(
        select(User).where(User.id == user_id)  # pyright: ignore[reportArgumentType]
    )
    user = user_row.scalar_one()

    profile_row = await session.execute(
        select(CandidateProfile)
        .options(selectinload(CandidateProfile.user))
        .where(CandidateProfile.user_id == user_id)  # type: ignore[arg-type]
    )
    profile = profile_row.scalar_one_or_none()

    apps: list[Application] = []
    if profile is not None and profile.id is not None:
        apps_row = await session.execute(
            select(Application)
            .where(Application.candidate_id == profile.id)  # pyright: ignore[reportArgumentType]
            .order_by(Application.created_at.desc())
        )
        apps = list(apps_row.scalars().all())

    audit_row = await session.execute(
        select(AuditLog)
        .where(  # pyright: ignore[reportArgumentType]
            AuditLog.actor_user_id == user_id,
            AuditLog.action.in_(CANDIDATE_VISIBLE_AUDIT_ACTIONS),
        )
        .order_by(AuditLog.created_at.desc())
    )
    audit_entries = list(audit_row.scalars().all())

    return user, profile, apps, audit_entries


def _serialize_export(
    user: User,
    profile: CandidateProfile | None,
    applications: list[Application],
    audit_entries: list[AuditLog],
) -> dict:
    """Build the ``data.json`` payload (GDPR portability bundle).

    Schema is intentionally explicit + versioned so future tooling can
    parse historic exports.
    """
    return {
        "schema_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
        },
        "profile": None
        if profile is None
        else {
            "id": profile.id,
            "full_name": profile.full_name,
            "email": profile.email,
            "phone": profile.phone,
            "linkedin_url": profile.linkedin_url,
            "resume_filename": profile.resume_path,
            "consent_given_at": (
                profile.consent_given_at.isoformat()
                if profile.consent_given_at
                else None
            ),
            "consent_policy_version": profile.consent_policy_version,
            "consent_ip": profile.consent_ip,
            "consent_user_agent": profile.consent_user_agent,
            "tos_accepted_at": (
                profile.tos_accepted_at.isoformat() if profile.tos_accepted_at else None
            ),
            "tos_version": profile.tos_version,
            "created_at": profile.created_at.isoformat(),
        },
        "applications": [
            {
                "id": app.id,
                "job_id": app.job_id,
                "status": app.status.value,
                "service_concept": app.service_concept,
                "salary_expectations": app.salary_expectations,
                "strength": app.strength,
                "growth_area": app.growth_area,
                "resume_filename": app.resume_path,
                "submitted_at": app.created_at.isoformat(),
                "updated_at": app.updated_at.isoformat(),
            }
            for app in applications
        ],
        "audit_log": [
            {
                "action": entry.action,
                "target_type": entry.target_type,
                "target_id": entry.target_id,
                "detail": entry.detail,
                "ip_address": entry.ip_address,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in audit_entries
        ],
    }


async def _build_zip_bytes(
    payload: dict,
    applications: list[Application],
    storage: StorageProvider,
) -> bytes:
    """Assemble the ZIP in memory.

    ``data.json`` at the top, then one ``resumes/<filename>`` per
    application that has a resume snapshot (#604). Best-effort on
    individual resume fetches — a storage outage on one resume
    shouldn't deny the whole export.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.json", json.dumps(payload, ensure_ascii=False, indent=2))

        for app in applications:
            if not app.resume_path:
                continue
            try:
                body = await storage.download_file(app.resume_path)
            except Exception:
                logger.exception(
                    "data_export_resume_fetch_failed",
                    extra={"resume_path": app.resume_path},
                )
                continue
            # Storage key is e.g. "resumes/abc123.pdf"; keep just the basename
            # so the archive's resumes/ subfolder is flat.
            arcname = (
                f"resumes/application_{app.id}_{app.resume_path.rsplit('/', 1)[-1]}"
            )
            zf.writestr(arcname, body)

    return buf.getvalue()


async def build_and_persist_export(
    user_id: int,
    session: AsyncSession,
    storage: StorageProvider,
) -> tuple[str, str]:
    """Run the full assemble → upload → persist sequence inside one session.

    Returns ``(raw_token, candidate_email)`` so the calling task can enqueue
    the notification email after commit. The candidate sees the raw token
    only in the email URL; the DB stores ``hash_token(raw_token)``.
    """
    user, profile, applications, audit_entries = await _gather_candidate_data(
        user_id, session
    )
    payload = _serialize_export(user, profile, applications, audit_entries)
    zip_bytes = await _build_zip_bytes(payload, applications, storage)

    # `exports/<user_id>/<uuid>.zip` — namespaced by user so the cleanup
    # cron in #10 can prefix-list. UUID keeps multiple retained exports
    # from colliding.
    storage_key = f"exports/{user_id}/{secrets.token_urlsafe(16)}.zip"
    await storage.upload_file(
        file_content=zip_bytes,
        file_name=storage_key,
        content_type="application/zip",
    )

    raw_token = secrets.token_urlsafe(32)
    record = DataExportRequest(
        token_hash=hash_token(raw_token),
        user_id=user_id,
        download_path=storage_key,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=DATA_EXPORT_TTL_HOURS),
        used=False,
    )
    session.add(record)
    await session.flush()

    return raw_token, user.email


async def get_export_request_by_token_hash(
    token_hash: str, session: AsyncSession
) -> DataExportRequest | None:
    """Look up a ``DataExportRequest`` row by its hashed download token."""
    result = await session.execute(
        select(DataExportRequest).where(  # pyright: ignore[reportArgumentType]
            DataExportRequest.token_hash == token_hash
        )
    )
    return result.scalar_one_or_none()


async def has_pending_export(user_id: int, session: AsyncSession) -> bool:
    """Per-user rate limit: is there an unused, unexpired export?

    Rather than introduce a Redis counter, count the unused rows that
    haven't timed out yet. One per 24h matches the issue spec.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(DataExportRequest).where(  # pyright: ignore[reportArgumentType]
            DataExportRequest.user_id == user_id,
            DataExportRequest.used == False,  # noqa: E712
            DataExportRequest.expires_at > now,
        )
    )
    return result.scalar_one_or_none() is not None
