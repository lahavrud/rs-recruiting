"""Admin endpoints for company approval and direct CRUD."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import client_ip, get_current_admin
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.pagination import DEFAULT_LIMIT, MAX_LIMIT, CursorPage
from src.core.infrastructure.transactions import transactional
from src.models import User
from src.schemas import (
    ActiveCompanyRead,
    ApprovedCompanyRead,
    CompanyProfileAdminCreate,
    CompanyProfileAdminUpdate,
    CompanyProfileRead,
    PendingCompanyRead,
)
from src.services.admin.companies import (
    approve_company,
    delete_active_company,
    list_active_companies,
    list_pending_companies,
    reject_company,
)
from src.services.admin.company_profiles import (
    admin_create_company,
    delete_orphan_company_profile,
    get_company_profile,
    update_company_profile,
)
from src.services.exceptions import (
    CompanyNotFoundError,
    CompanyNotPendingError,
    EmailAlreadyExistsError,
    InvalidCursorError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/companies", response_model=CursorPage[ActiveCompanyRead])
async def get_active_companies(
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    sort: Literal["name", "created_at"] = Query(default="created_at"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[ActiveCompanyRead]:
    """List active companies, sorted by `sort`/`order`, cursor-paginated."""
    try:
        return await list_active_companies(
            session, cursor=cursor, limit=limit, sort=sort, order=order
        )
    except InvalidCursorError as exc:
        raise service_exception_to_http(exc) from exc


@router.post(
    "/companies", response_model=CompanyProfileRead, status_code=status.HTTP_201_CREATED
)
async def create_company_directly(
    data: CompanyProfileAdminCreate,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CompanyProfileRead:
    """Create a CompanyProfile directly (user_id=null). For pre-onboarding companies."""
    async with transactional(session):
        return await admin_create_company(data, session)


@router.get("/companies/profile/{profile_id}", response_model=CompanyProfileRead)
async def get_company_profile_endpoint(
    profile_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CompanyProfileRead:
    """Fetch a single CompanyProfile by its primary key."""
    try:
        return await get_company_profile(profile_id, session)
    except CompanyNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.put("/companies/profile/{profile_id}", response_model=CompanyProfileRead)
async def update_company_profile_endpoint(
    profile_id: int,
    data: CompanyProfileAdminUpdate,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CompanyProfileRead:
    """Partially update a CompanyProfile."""
    try:
        async with transactional(session):
            return await update_company_profile(profile_id, data, session)
    except (CompanyNotFoundError, EmailAlreadyExistsError) as e:
        raise service_exception_to_http(e) from e


@router.delete(
    "/companies/profile/{profile_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_orphan_company(
    profile_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an admin-created CompanyProfile that has no user account."""
    try:
        async with transactional(session):
            await delete_orphan_company_profile(profile_id, session)
    except (CompanyNotFoundError, CompanyNotPendingError) as e:
        raise service_exception_to_http(e) from e


@router.delete("/companies/{company_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_user_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Hard-delete a company and all its jobs and applications."""
    try:
        async with transactional(session):
            await delete_active_company(
                company_user_id,
                session,
                actor_user_id=current_admin.id,
                ip_address=client_ip(request),
            )
    except CompanyNotFoundError as e:
        raise service_exception_to_http(e) from e


@router.get("/companies/pending", response_model=CursorPage[PendingCompanyRead])
async def get_pending_companies(
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[PendingCompanyRead]:
    """List pending company registrations, newest first, cursor-paginated."""
    try:
        return await list_pending_companies(session, cursor=cursor, limit=limit)
    except InvalidCursorError as exc:
        raise service_exception_to_http(exc) from exc


@router.post(
    "/companies/{company_user_id}/approve",
    response_model=ApprovedCompanyRead,
    status_code=status.HTTP_200_OK,
)
async def approve_company_registration(
    company_user_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> ApprovedCompanyRead:
    """Approve a company registration."""
    try:
        async with transactional(session):
            result = await approve_company(
                company_user_id,
                session,
                actor_user_id=current_admin.id,
                ip_address=client_ip(request),
            )
            return ApprovedCompanyRead.model_validate(result)
    except (CompanyNotFoundError, CompanyNotPendingError) as e:
        logger.warning(
            "admin company approve failed: %s",
            e,
            extra={
                "company_user_id": company_user_id,
                "error_type": type(e).__name__,
            },
        )
        raise service_exception_to_http(e) from e


@router.post(
    "/companies/{company_user_id}/reject", status_code=status.HTTP_204_NO_CONTENT
)
async def reject_company_registration(
    company_user_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Reject a company registration."""
    try:
        async with transactional(session):
            await reject_company(
                company_user_id,
                session,
                actor_user_id=current_admin.id,
                ip_address=client_ip(request),
            )
    except (CompanyNotFoundError, CompanyNotPendingError) as e:
        logger.warning(
            "admin company reject failed: %s",
            e,
            extra={
                "company_user_id": company_user_id,
                "error_type": type(e).__name__,
            },
        )
        raise service_exception_to_http(e) from e
