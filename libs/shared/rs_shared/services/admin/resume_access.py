"""Audit trail for admins opening a candidate's resume.

A resume is personal data, so each view is recorded against the candidate it
belongs to: the row answers "who looked at this person's CV, and when?".
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import Application, AuditLog, CandidateProfile
from rs_shared.services.utils.audit import record_audit_event

_logger = logging.getLogger(__name__)

RESUME_VIEW = "candidate.resume_view"

# Repeat opens by the same admin within this window collapse into one row, so
# a candidate under active review doesn't have their timeline (latest 50
# rows) filled with views. A different admin, or a later visit, still writes.
VIEW_DEDUPE_WINDOW = timedelta(minutes=10)


async def _resume_owner(
    storage_key: str, session: AsyncSession
) -> tuple[int, int | None] | None:
    """``(candidate_id, application_id)`` for the file, or None if no row has it.

    The profile's current resume wins. Otherwise the file is a snapshot taken
    for an application, and that application is named too (the earliest one,
    when several applications reuse the same snapshot).
    """
    # Keys are minted per upload, so a key maps to one candidate; limit(1)
    # rather than scalar_one_or_none() keeps a duplicate from turning a served
    # CV into a 500.
    candidate_id = (
        await session.execute(
            select(CandidateProfile.id)
            .where(CandidateProfile.resume_path == storage_key)  # pyright: ignore[reportArgumentType]
            .order_by(CandidateProfile.id)
            .limit(1)
        )
    ).scalar()
    if candidate_id is not None:
        return candidate_id, None

    row = (
        await session.execute(
            select(Application.candidate_id, Application.id)
            .where(Application.resume_path == storage_key)  # pyright: ignore[reportArgumentType]
            .order_by(Application.id)
            .limit(1)
        )
    ).first()
    return (row[0], row[1]) if row else None


async def _viewed_recently(
    session: AsyncSession, candidate_id: int, actor_user_id: int | None
) -> bool:
    since = datetime.now(timezone.utc) - VIEW_DEDUPE_WINDOW
    found = await session.execute(
        select(AuditLog.id)
        .where(
            AuditLog.action == RESUME_VIEW,  # pyright: ignore[reportArgumentType]
            AuditLog.target_type == "CandidateProfile",  # pyright: ignore[reportArgumentType]
            AuditLog.target_id == candidate_id,  # pyright: ignore[reportArgumentType]
            AuditLog.actor_user_id == actor_user_id,  # pyright: ignore[reportArgumentType]
            AuditLog.created_at >= since,  # pyright: ignore[reportArgumentType,reportOperatorIssue]
        )
        .limit(1)
    )
    return found.first() is not None


async def audit_resume_view(
    session: AsyncSession,
    file_key: str,
    *,
    actor_user_id: int | None,
    ip_address: str | None = None,
) -> None:
    """Record that ``actor_user_id`` opened the resume stored as ``resumes/<file_key>``.

    A file no profile or application points at has no one to attribute the
    view to, so it is logged instead of audited. A repeat open by the same
    admin within ``VIEW_DEDUPE_WINDOW`` is already covered by the earlier row.
    """
    owner = await _resume_owner(f"resumes/{file_key}", session)
    if owner is None:
        _logger.warning("resume_view_without_owner", extra={"file_key": file_key})
        return
    candidate_id, application_id = owner
    if await _viewed_recently(session, candidate_id, actor_user_id):
        return
    await record_audit_event(
        session,
        actor_user_id=actor_user_id,
        action=RESUME_VIEW,
        target_type="CandidateProfile",
        target_id=candidate_id,
        detail=f"application_id={application_id}" if application_id else None,
        ip_address=ip_address,
    )
