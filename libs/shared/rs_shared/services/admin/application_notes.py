"""Admin notes on an application: internal, never shown to the candidate."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import Application
from rs_shared.schemas import ApplicationRead
from rs_shared.services.exceptions import ApplicationNotFoundError
from rs_shared.services.utils.audit import record_audit_event


async def update_application_notes(
    application_id: int,
    admin_notes: str | None,
    session: AsyncSession,
    actor_user_id: int | None = None,
    ip_address: str | None = None,
) -> ApplicationRead:
    """Distinct from `update_application_status` — skips the status-transition
    checks and rejection email, since notes are an internal admin annotation
    rather than a candidate-facing state change. The edit is audited without
    the text, which is free-form and may hold personal data.

    Raises:
        ApplicationNotFoundError: If application not found.
    """
    result = await session.execute(
        select(Application).where(Application.id == application_id)  # pyright: ignore[reportArgumentType]
    )
    application = result.scalar_one_or_none()
    if not application:
        raise ApplicationNotFoundError(
            f"Application with ID {application_id} not found"
        )

    if application.admin_notes != admin_notes:
        await record_audit_event(
            session,
            actor_user_id=actor_user_id,
            action="application.notes_update",
            target_type="Application",
            target_id=application_id,
            ip_address=ip_address,
        )
    application.admin_notes = admin_notes
    application.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(application)
    return ApplicationRead.model_validate(application)
