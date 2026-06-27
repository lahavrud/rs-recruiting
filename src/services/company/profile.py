"""Company-facing service functions (self-service profile, stats, data export)."""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.services.storage import StorageProvider
from src.enums import JobStatus
from src.models import Application, CompanyProfile, Job, User
from src.schemas import (
    CompanyDataExport,
    CompanyProfileRead,
    CompanyProfileSelfUpdate,
    CompanyStats,
    JobRead,
    UserRead,
)

logger = logging.getLogger(__name__)


async def get_company_profile(profile: CompanyProfile) -> CompanyProfileRead:
    return CompanyProfileRead.model_validate(profile)


async def update_company_profile(
    profile: CompanyProfile,
    data: CompanyProfileSelfUpdate,
    session: AsyncSession,
) -> CompanyProfileRead:
    if data.name is not None:
        profile.name = data.name
    if data.address is not None:
        profile.address = data.address
    if data.contact_first_name is not None:
        profile.contact_first_name = data.contact_first_name
    if data.contact_last_name is not None:
        profile.contact_last_name = data.contact_last_name
    if data.contact_mobile_phone is not None:
        profile.contact_mobile_phone = data.contact_mobile_phone
    if "contact_landline_phone" in data.model_fields_set:
        profile.contact_landline_phone = data.contact_landline_phone
    await session.flush()
    return CompanyProfileRead.model_validate(profile)


async def get_company_stats(company_id: int, session: AsyncSession) -> CompanyStats:
    job_rows = list(
        (
            await session.execute(
                select(Job.status, func.count().label("cnt"))
                .where(Job.company_id == company_id)  # pyright: ignore[reportArgumentType]
                .group_by(Job.status)
            )
        ).all()
    )
    status_counts: dict[str, int] = {row[0]: row[1] for row in job_rows}
    active_jobs = status_counts.get(JobStatus.PUBLISHED, 0)
    pending_jobs = status_counts.get(JobStatus.PENDING_APPROVAL, 0)
    closed_jobs = status_counts.get(JobStatus.CLOSED, 0)

    job_ids_result = await session.execute(
        select(Job.id).where(Job.company_id == company_id)  # pyright: ignore[reportArgumentType]
    )
    job_ids = [row[0] for row in job_ids_result.all()]

    applications_by_status: dict[str, int] = {}
    total_applications = 0
    if job_ids:
        app_rows = list(
            (
                await session.execute(
                    select(Application.status, func.count().label("cnt"))
                    .where(Application.job_id.in_(job_ids))  # pyright: ignore[reportArgumentType]
                    .group_by(Application.status)
                )
            ).all()
        )
        for status, cnt in app_rows:
            applications_by_status[status] = cnt
            total_applications += cnt

    return CompanyStats(
        active_jobs=active_jobs,
        pending_jobs=pending_jobs,
        closed_jobs=closed_jobs,
        total_applications=total_applications,
        applications_by_status=applications_by_status,
    )


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
