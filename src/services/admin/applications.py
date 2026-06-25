"""Admin service functions for application (match) management."""

from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.config import settings
from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.core.infrastructure.pagination import (
    CursorPage,
    SortValue,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.enums import ApplicationStatus
from src.models import Application, CandidateProfile
from src.schemas import ApplicationRead, ApplicationWithDetails, AuditLogRead
from src.services.exceptions import (
    ApplicationNotEditableError,
    ApplicationNotFoundError,
)
from src.services.utils.audit import list_audit_events, record_audit_event
from src.templates.email import build_application_rejection_html

ApplicationSortColumn = Literal["name", "created_at", "status"]

_STATUS_PRIORITY: dict[ApplicationStatus, int] = {
    ApplicationStatus.NEW: 0,
    ApplicationStatus.APPROVED_BY_ADMIN: 1,
    ApplicationStatus.HIRED: 2,
    ApplicationStatus.REJECTED: 3,
    ApplicationStatus.WITHDRAWN: 4,
    ApplicationStatus.JOB_CLOSED: 5,
}


def _sort_column(column: ApplicationSortColumn) -> Any:
    if column == "name":
        return CandidateProfile.full_name
    if column == "status":
        return case(
            _STATUS_PRIORITY,  # pyright: ignore[reportArgumentType]
            value=Application.status,
            else_=len(_STATUS_PRIORITY),
        )
    return Application.created_at


def _sort_value(application: Application, column: ApplicationSortColumn) -> SortValue:
    if column == "name":
        return application.candidate.full_name
    if column == "status":
        return _STATUS_PRIORITY.get(application.status, len(_STATUS_PRIORITY))
    return application.created_at


async def list_applications(
    session: AsyncSession,
    *,
    status: ApplicationStatus | None = None,
    job_id: int | None = None,
    candidate_id: int | None = None,
    cursor: str | None = None,
    limit: int | None = None,
    sort: ApplicationSortColumn = "created_at",
    order: Literal["asc", "desc"] = "desc",
    sort2: ApplicationSortColumn | None = None,
    order2: Literal["asc", "desc"] = "desc",
) -> CursorPage[ApplicationWithDetails]:
    """`sort="name"` sorts by the applying candidate's full name.

    `sort="status"` groups by status — needs-attention first when
    `order="asc"`, last when `order="desc"`.

    `sort2` adds a second, independent sort column as a tiebreaker — e.g.
    `sort="status"` with `sort2="created_at"` groups by status, then orders
    by date within each group. A column can't be paired with itself.
    """
    if sort2 == sort:
        sort2 = None
    page_size = clamp_limit(limit)
    base = select(Application).options(
        selectinload(Application.job),  # pyright: ignore[reportArgumentType]
        selectinload(Application.candidate),  # pyright: ignore[reportArgumentType]
    )
    if status is not None:
        base = base.where(Application.status == status)  # pyright: ignore[reportArgumentType]
    if job_id is not None:
        base = base.where(Application.job_id == job_id)  # pyright: ignore[reportArgumentType]
    if candidate_id is not None:
        base = base.where(Application.candidate_id == candidate_id)  # pyright: ignore[reportArgumentType]

    if sort == "name" or sort2 == "name":
        base = base.join(
            CandidateProfile,
            Application.candidate_id == CandidateProfile.id,  # pyright: ignore[reportArgumentType]
        )

    sort_col = _sort_column(sort)
    secondary_col = _sort_column(sort2) if sort2 is not None else None
    sort_key = sort if sort2 is None else f"{sort},{sort2}"

    query = apply_cursor(
        base,
        sort_col=sort_col,  # pyright: ignore[reportArgumentType]
        id_col=Application.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
        sort_key=sort_key,
        direction=order,
        secondary_col=secondary_col,  # pyright: ignore[reportArgumentType]
        secondary_direction=order2,
    )
    rows = list((await session.execute(query)).scalars().all())

    def _cursor_key(
        a: Application,
    ) -> tuple[SortValue, int] | tuple[SortValue, SortValue | None, int]:
        if sort2 is not None:
            return _sort_value(a, sort), _sort_value(a, sort2), a.id
        return _sort_value(a, sort), a.id

    return build_cursor_page(
        rows,
        serializer=ApplicationWithDetails.model_validate,
        cursor_key=_cursor_key,
        limit=page_size,
        sort_key=sort_key,
    )


async def get_application(
    application_id: int, session: AsyncSession
) -> ApplicationWithDetails:
    application = await get_by_id_or_raise(
        session,
        Application,
        application_id,
        lambda pk: ApplicationNotFoundError(f"Application with ID {pk} not found"),
        options=[
            selectinload(Application.job),  # pyright: ignore[reportArgumentType]
            selectinload(Application.candidate),  # pyright: ignore[reportArgumentType]
        ],
    )
    return ApplicationWithDetails.model_validate(application)


async def get_application_activity(
    application_id: int,
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[AuditLogRead]:
    """Activity timeline for an application's record pane (status-change audit rows).

    The application's own creation is never written to the audit log (it
    isn't an admin action), so a synthetic "submitted" entry is appended on
    the last page, dated to `Application.created_at`, to anchor the
    timeline's oldest end.

    Raises:
        ApplicationNotFoundError: If no application with that id exists.
    """
    application = await get_by_id_or_raise(
        session,
        Application,
        application_id,
        lambda pk: ApplicationNotFoundError(f"Application with ID {pk} not found"),
    )
    page = await list_audit_events(
        session,
        target_type="Application",
        target_id=application_id,
        cursor=cursor,
        limit=limit,
    )
    if page.next_cursor is None:
        page.items.append(
            AuditLogRead(
                id=-application_id,
                actor_user_id=None,
                action="application.submitted",
                target_type="Application",
                target_id=application_id,
                detail=None,
                ip_address=None,
                created_at=application.created_at,
            )
        )
    return page


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
    if newly_rejected:
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


async def update_application_notes(
    application_id: int,
    admin_notes: str | None,
    session: AsyncSession,
) -> ApplicationRead:
    """Distinct from `update_application_status` — skips the status-transition
    checks, audit event, and rejection email, since notes are an internal
    admin annotation rather than a candidate-facing state change.

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

    application.admin_notes = admin_notes
    application.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(application)
    return ApplicationRead.model_validate(application)


async def delete_application(
    application_id: int,
    session: AsyncSession,
) -> None:
    """Removes only the job <-> candidate link; candidate profile and job are untouched.

    Raises:
        ApplicationNotFoundError: If application not found
    """
    application = await session.get(Application, application_id)
    if application is None:
        raise ApplicationNotFoundError(
            f"Application with ID {application_id} not found"
        )
    await session.delete(application)
    await session.commit()
