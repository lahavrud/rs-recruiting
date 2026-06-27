"""Application status-update logic for admin service.

Split out of applications.py to satisfy the 300-line file cap.
Exercised end-to-end via tests/services/admin/test_applications.py.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.config import settings
from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.enums import ApplicationStatus
from src.models import Application
from src.schemas import ApplicationRead
from src.services.exceptions import (
    ApplicationNotEditableError,
    ApplicationNotFoundError,
)
from src.services.utils.audit import record_audit_event
from src.templates.email import build_application_rejection_html


async def update_application_status(
    application_id: int,
    new_status: ApplicationStatus,
    session: AsyncSession,
    admin_notes: str | None = None,
    *,
    actor_user_id: int | None = None,
    ip_address: str | None = None,
) -> tuple[ApplicationRead, list[dict[str, str]]]:
    """Update an application's status and optionally add admin notes.

    Enforces valid status transitions. Returns the updated application and
    a list of email payloads to be enqueued by the caller *after* the
    surrounding DB transaction has been committed, so emails are never sent
    for changes that were subsequently rolled back.

    Args:
        application_id: ID of the application to update
        new_status: The target status
        session: Database session
        admin_notes: Optional notes from the admin

    Returns:
        Tuple of (updated ApplicationRead, list of email payload dicts).
        Each payload dict has keys: ``to``, ``subject``, ``body``, ``html_body``.

    Raises:
        ApplicationNotFoundError: If application not found
    """
    application = await get_by_id_or_raise(
        session,
        Application,
        application_id,
        lambda pk: ApplicationNotFoundError(f"Application with ID {pk} not found"),
        options=[
            selectinload(Application.candidate),  # pyright: ignore[reportArgumentType]
            selectinload(Application.job),  # pyright: ignore[reportArgumentType]
        ],
    )

    old_status = application.status

    if old_status == ApplicationStatus.WITHDRAWN:
        raise ApplicationNotEditableError(
            "Cannot change status of a withdrawn application"
        )

    application.status = new_status
    if admin_notes is not None:
        application.admin_notes = admin_notes
    application.updated_at = datetime.now(timezone.utc)
    await session.flush()

    if old_status != new_status:
        await record_audit_event(
            session,
            actor_user_id=actor_user_id,
            action="application.status_change",
            target_type="Application",
            target_id=application_id,
            detail=f"{old_status.value}->{new_status.value}",
            ip_address=ip_address,
        )

    email_payloads: list[dict[str, str]] = []
    newly_rejected = (
        new_status == ApplicationStatus.REJECTED
        and old_status != ApplicationStatus.REJECTED
    )
    if newly_rejected and application.pushed_by_admin_id is None:
        candidate = application.candidate
        job = application.job
        plain = (
            f"{candidate.full_name} שלום,\n\n"
            "ראשית, אנו רוצים להודות לך על הזמן שהשקעת בהגשת המועמדות ועל העניין "
            "שגילית בתפקיד.\n\n"
            "לאחר בחינה מעמיקה של קורות החיים מול צרכי הלקוח, הרינו לעדכנך כי בשלב "
            "זה הוחלט לבחון מועמדים שרקעם התעסוקתי תואם באופן מדויק יותר את הפרופיל "
            "המבוקש.\n\n"
            "יחד עם זאת, התרשמנו מהפרופיל המקצועי ונשמח לשמור את קורות החיים אצלנו. "
            "במידה ותעמוד על הפרק משרה שתהלם את הכישורים והניסיון הרלוונטיים, "
            "נשמח מאוד ליצור קשר.\n\n"
            "שוב תודה, והרבה הצלחה בהמשך הדרך המקצועית.\n\n"
            "בברכה,\nצוות RS Recruiting\n\n"
            f"סבורים שחלה טעות? ניתן לפנות אלינו: {settings.support_email}"
        )
        email_payloads = [
            {
                "to": candidate.email,
                "subject": f"עדכון בנוגע למועמדותך למשרת {job.title} — RS Recruiting",
                "body": plain,
                "html_body": build_application_rejection_html(
                    candidate_name=candidate.full_name,
                    job_title=job.title,
                ),
            }
        ]

    return ApplicationRead.model_validate(application), email_payloads
