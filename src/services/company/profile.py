"""Company-facing service functions (self-service data export)."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.services.storage import StorageProvider
from src.models import CompanyProfile, Job, User
from src.schemas import (
    CompanyDataExport,
    CompanyProfileRead,
    JobRead,
    UserRead,
)

logger = logging.getLogger(__name__)


async def _resolve_url(storage: StorageProvider, identifier: str | None) -> str | None:
    """Best-effort presign — return None on failure rather than aborting the export.

    Storage failures should not block a compliance request.
    """
    if not identifier:
        return None
    try:
        return await storage.get_file_url(identifier)
    except Exception:
        logger.exception("Failed to resolve URL for key %s", identifier)
        return None


async def export_company_data(
    user: User,
    profile: CompanyProfile,
    session: AsyncSession,
    storage: StorageProvider,
) -> CompanyDataExport:
    """Build the right-to-portability payload for the calling company."""
    profile_read = CompanyProfileRead.model_validate(profile)
    profile_read.logo_url = await _resolve_url(storage, profile.logo_url)
    profile_read.agreement_signature_url = await _resolve_url(
        storage, profile.agreement_signature_url
    )
    profile_read.contract_pdf_url = await _resolve_url(
        storage, profile.contract_pdf_url
    )

    result = await session.execute(
        select(Job).where(Job.company_id == profile.id).order_by(Job.created_at.desc())  # pyright: ignore[reportArgumentType]
    )
    jobs = [JobRead.model_validate(j) for j in result.scalars().all()]

    return CompanyDataExport(
        exported_at=datetime.now(timezone.utc),
        user=UserRead.model_validate(user),
        company_profile=profile_read,
        jobs=jobs,
    )
