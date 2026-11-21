"""Audit trail for hard-deleted applications.

An application is removed directly (admin delete) or by cascade when its job
or company is deleted. Each removal writes one ``application.delete`` row
whose detail names the candidate. That matters because the candidate's
activity timeline finds application events through the ``Application`` table,
which no longer has the row: ``deleted_application_ids`` recovers the ids from
the delete rows instead, so the history stays visible after the delete.

Details hold ids and the status only. The audit log outlives the application
and possibly the candidate, so it must not carry their personal data.
"""

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import Application, AuditLog
from rs_shared.services.utils.audit import record_audit_event

APPLICATION_DELETE = "application.delete"


def _delete_detail(application: Application, cause: str | None) -> str:
    # job_id first and candidate_id followed by a comma: deleted_application_ids
    # matches on exactly this prefix.
    detail = (
        f"job_id={application.job_id},candidate_id={application.candidate_id},"
        f"status={application.status.value}"
    )
    return f"{detail},cause={cause}" if cause else detail


async def audit_application_deletes(
    session: AsyncSession,
    *conditions: Any,
    actor_user_id: int | None = None,
    ip_address: str | None = None,
    cause: str | None = None,
) -> None:
    """Write an ``application.delete`` row per application matching ``conditions``.

    Call it before the delete (or the parent delete that cascades to the
    applications), inside the same transaction. ``cause`` names the parent
    delete for cascades, e.g. ``"job_delete"``.
    """
    applications = (
        (await session.execute(select(Application).where(*conditions))).scalars().all()
    )
    for application in applications:
        await record_audit_event(
            session,
            actor_user_id=actor_user_id,
            action=APPLICATION_DELETE,
            target_type="Application",
            target_id=application.id,  # pyright: ignore[reportArgumentType]
            detail=_delete_detail(application, cause),
            ip_address=ip_address,
        )


def deleted_application_ids(candidate_id: int) -> Select[Any]:
    """Ids of the candidate's applications that were deleted, from their audit rows."""
    return select(AuditLog.target_id).where(
        AuditLog.action == APPLICATION_DELETE,  # pyright: ignore[reportArgumentType]
        AuditLog.target_type == "Application",  # pyright: ignore[reportArgumentType]
        AuditLog.detail.like(f"job_id=%,candidate_id={candidate_id},%"),  # pyright: ignore[reportAttributeAccessIssue,reportOptionalMemberAccess]
    )
