"""Company self-service endpoints."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.infrastructure.dependencies import client_ip, get_current_company
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.core.services.storage import get_storage_provider
from rs_shared.models import CompanyProfile, User
from rs_shared.schemas import (
    CompanyDataExport,
    CompanyProfileRead,
    CompanyProfileSelfUpdate,
)
from rs_shared.schemas.companies import CompanyStats
from rs_shared.services.company.profile import (
    export_company_data,
    get_company_profile,
    get_company_stats,
    update_company_profile,
)

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/me", response_model=CompanyProfileRead)
async def get_my_company_profile(
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
) -> CompanyProfileRead:
    """Return the authenticated company's profile."""
    _, profile = current_company
    return await get_company_profile(profile)


@router.patch("/me", response_model=CompanyProfileRead)
async def update_my_company_profile(
    data: CompanyProfileSelfUpdate,
    request: Request,
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> CompanyProfileRead:
    """Update mutable fields on the authenticated company's profile."""
    user, profile = current_company
    async with transactional(session):
        return await update_company_profile(
            profile, data, session, actor_user_id=user.id, ip_address=client_ip(request)
        )


@router.get("/me/stats", response_model=CompanyStats)
async def get_my_company_stats(
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> CompanyStats:
    """Return aggregated stats for the authenticated company's dashboard."""
    _, profile = current_company
    return await get_company_stats(profile.id or 0, session)


@router.get("/me/export", response_model=CompanyDataExport)
async def export_my_company_data(
    current_company: tuple[User, CompanyProfile] = Depends(get_current_company),
    session: AsyncSession = Depends(get_session),
) -> CompanyDataExport:
    """Right-to-data-portability export for the authenticated company."""
    user, profile = current_company
    return await export_company_data(user, profile, session, get_storage_provider())
