"""Admin endpoints for application (match) management."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import client_ip, get_current_admin
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.pagination import DEFAULT_LIMIT, MAX_LIMIT, CursorPage
from src.core.infrastructure.transactions import defer_after_commit, transactional
from src.core.tasks import enqueue_email_task
from src.enums import ApplicationStatus
from src.models import User
from src.schemas import (
    ApplicationNotesUpdate,
    ApplicationRead,
    ApplicationStatusUpdate,
    ApplicationWithDetails,
    AuditLogRead,
)
from src.services.admin.applications import (
    delete_application,
    get_application,
    get_application_activity,
    list_applications,
    update_application_notes,
    update_application_status,
)
from src.services.exceptions import (
    ApplicationNotEditableError,
    ApplicationNotFoundError,
    InvalidCursorError,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/applications", response_model=CursorPage[ApplicationWithDetails])
async def get_applications(
    status: ApplicationStatus | None = None,
    job_id: int | None = None,
    candidate_id: int | None = None,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    sort: Literal["name", "created_at", "status"] = Query(default="created_at"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    sort2: Literal["name", "created_at", "status"] | None = Query(default=None),
    order2: Literal["asc", "desc"] = Query(default="desc"),
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[ApplicationWithDetails]:
    """List applications with optional filters, sorted by `sort`/`order`.

    `sort2`/`order2` add a second sort column as a tiebreaker — e.g.
    `sort=status&sort2=created_at` groups by status, then by date.
    Cursor-paginated.
    """
    try:
        return await list_applications(
            session,
            status=status,
            job_id=job_id,
            candidate_id=candidate_id,
            cursor=cursor,
            limit=limit,
            sort=sort,
            order=order,
            sort2=sort2,
            order2=order2,
        )
    except InvalidCursorError as exc:
        raise service_exception_to_http(exc) from exc


@router.get("/applications/{application_id}", response_model=ApplicationWithDetails)
async def get_application_detail(
    application_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> ApplicationWithDetails:
    """Get a single application with full details."""
    try:
        return await get_application(application_id, session)
    except ApplicationNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.get(
    "/applications/{application_id}/activity",
    response_model=CursorPage[AuditLogRead],
)
async def get_application_activity_endpoint(
    application_id: int,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[AuditLogRead]:
    """Activity timeline: audit rows for this application (status changes)."""
    try:
        return await get_application_activity(
            application_id, session, cursor=cursor, limit=limit
        )
    except (ApplicationNotFoundError, InvalidCursorError) as exc:
        raise service_exception_to_http(exc) from exc


@router.put(
    "/applications/{application_id}/status",
    response_model=ApplicationRead,
    status_code=status.HTTP_200_OK,
)
async def update_application_status_endpoint(
    application_id: int,
    body: ApplicationStatusUpdate,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> ApplicationRead:
    """Update application status. Emails (if any) enqueued after commit."""
    try:
        async with transactional(session):
            result, email_payloads = await update_application_status(
                application_id,
                body.status,
                session,
                admin_notes=body.admin_notes,
                actor_user_id=current_admin.id,
                ip_address=client_ip(request),
            )
            for payload in email_payloads:
                defer_after_commit(lambda p=payload: enqueue_email_task(**p))
    except ApplicationNotFoundError as e:
        raise service_exception_to_http(e) from e
    except ApplicationNotEditableError as e:
        raise service_exception_to_http(e) from e

    return result


@router.put(
    "/applications/{application_id}/notes",
    response_model=ApplicationRead,
    status_code=status.HTTP_200_OK,
)
async def update_application_notes_endpoint(
    application_id: int,
    body: ApplicationNotesUpdate,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> ApplicationRead:
    """Update only the admin_notes field. Does not change status or send email."""
    try:
        async with transactional(session):
            return await update_application_notes(
                application_id, body.admin_notes, session
            )
    except ApplicationNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application_endpoint(
    application_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an application record. The candidate profile is preserved."""
    try:
        await delete_application(application_id, session)
    except ApplicationNotFoundError as e:
        raise service_exception_to_http(e) from e
