"""Admin service functions for application (match) management."""

from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.core.infrastructure.pagination import (
    CursorPage,
    SortValue,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.core.matching import cosine_similarity_score
from src.enums import ApplicationStatus
from src.models import Application, CandidateProfile, Job
from src.schemas import ApplicationRead, ApplicationWithDetails, AuditLogRead
from src.services.admin._application_status import (
    update_application_status as update_application_status,
)
from src.services.exceptions import ApplicationNotFoundError
from src.services.utils.audit import list_audit_events

ApplicationSortColumn = Literal["name", "created_at", "status", "score"]

_SCORE_SORT_LIMIT = 200

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
            *[(Application.status == k, v) for k, v in _STATUS_PRIORITY.items()],
            else_=len(_STATUS_PRIORITY),
        )
    return Application.created_at


def _sort_value(application: Application, column: ApplicationSortColumn) -> SortValue:
    if column == "name":
        return application.candidate.full_name
    if column == "status":
        return _STATUS_PRIORITY.get(application.status, len(_STATUS_PRIORITY))
    return application.created_at


async def _list_applications_by_score(
    session: AsyncSession,
    *,
    status: ApplicationStatus | None = None,
    job_id: int | None = None,
    candidate_id: int | None = None,
) -> CursorPage[ApplicationWithDetails]:
    """Return applications ranked by AI match score, best first.

    Only includes rows where both the candidate and job have embeddings.
    Returns a single non-paginated page (next_cursor=None).
    """
    distance_expr = CandidateProfile.embedding.cosine_distance(Job.embedding)
    stmt = (
        select(Application, distance_expr.label("dist"))
        .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)  # pyright: ignore[reportArgumentType]
        .join(Job, Application.job_id == Job.id)  # pyright: ignore[reportArgumentType]
        .options(
            selectinload(Application.job).selectinload(Job.company),  # pyright: ignore[reportArgumentType]
            selectinload(Application.candidate),  # pyright: ignore[reportArgumentType]
        )
        .where(
            CandidateProfile.embedding.is_not(None),  # pyright: ignore[reportArgumentType]
            Job.embedding.is_not(None),  # pyright: ignore[reportArgumentType]
        )
    )
    if status is not None:
        stmt = stmt.where(Application.status == status)  # pyright: ignore[reportArgumentType]
    if job_id is not None:
        stmt = stmt.where(Application.job_id == job_id)  # pyright: ignore[reportArgumentType]
    if candidate_id is not None:
        stmt = stmt.where(Application.candidate_id == candidate_id)  # pyright: ignore[reportArgumentType]
    stmt = stmt.order_by(distance_expr.asc()).limit(_SCORE_SORT_LIMIT)

    rows = (await session.execute(stmt)).all()
    items: list[ApplicationWithDetails] = []
    for app, dist in rows:
        schema = ApplicationWithDetails.model_validate(app)
        schema.ai_score = cosine_similarity_score(dist)
        items.append(schema)
    return CursorPage(items=items, next_cursor=None)


async def list_applications(
    session: AsyncSession,
    *,
    status: ApplicationStatus | None = None,
    job_id: int | None = None,
    candidate_id: int | None = None,
    q: str | None = None,
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

    `q`, when given, case-insensitively substring-matches candidate
    name/email/phone and job title.
    """
    if sort == "score":
        return await _list_applications_by_score(
            session, status=status, job_id=job_id, candidate_id=candidate_id
        )
    if sort2 == sort:
        sort2 = None
    page_size = clamp_limit(limit)
    base = select(Application).options(
        selectinload(Application.job).selectinload(Job.company),  # pyright: ignore[reportArgumentType]
        selectinload(Application.candidate),  # pyright: ignore[reportArgumentType]
    )
    if status is not None:
        base = base.where(Application.status == status)  # pyright: ignore[reportArgumentType]
    if job_id is not None:
        base = base.where(Application.job_id == job_id)  # pyright: ignore[reportArgumentType]
    if candidate_id is not None:
        base = base.where(Application.candidate_id == candidate_id)  # pyright: ignore[reportArgumentType]

    needs_candidate_join = (sort == "name" or sort2 == "name") or bool(q and q.strip())
    if needs_candidate_join:
        base = base.join(
            CandidateProfile,
            Application.candidate_id == CandidateProfile.id,  # pyright: ignore[reportArgumentType]
        )

    if q and q.strip():
        term = f"%{q.strip()}%"
        base = base.join(Job, Application.job_id == Job.id).where(  # pyright: ignore[reportArgumentType]
            or_(
                CandidateProfile.full_name.ilike(term),  # pyright: ignore[reportArgumentType]
                CandidateProfile.email.ilike(term),  # pyright: ignore[reportArgumentType]
                CandidateProfile.phone.ilike(term),  # pyright: ignore[reportArgumentType]
                Job.title.ilike(term),  # pyright: ignore[reportArgumentType]
            )
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
            selectinload(Application.job).selectinload(Job.company),  # pyright: ignore[reportArgumentType]
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
        action = (
            "application.pushed_by_admin"
            if application.pushed_by_admin_id is not None
            else "application.submitted"
        )
        page.items.append(
            AuditLogRead(
                id=-application_id,
                actor_user_id=application.pushed_by_admin_id,
                action=action,
                target_type="Application",
                target_id=application_id,
                detail=None,
                ip_address=None,
                created_at=application.created_at,
            )
        )
    return page


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
