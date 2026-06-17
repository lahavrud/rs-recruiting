"""Admin service layer for company management."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.core.infrastructure.transactions import defer_after_commit
from src.core.services.storage import get_storage_provider
from src.core.tasks import enqueue_email_task
from src.enums import UserRole
from src.models import (
    ActivationToken,
    CompanyProfile,
    User,
)
from src.schemas import (
    ActiveCompanyRead,
    CompanyProfileRead,
    PendingCompanyRead,
    UserRead,
)
from src.services.admin._helpers import validate_company_user_pending
from src.services.admin.company_approval import approve_company  # re-exported
from src.services.exceptions import CompanyNotFoundError
from src.services.utils.audit import record_audit_event
from src.templates.email import build_rejection_html

__all__ = [
    "approve_company",
    "delete_active_company",
    "get_all_admin_emails",
    "list_active_companies",
    "list_pending_companies",
    "reject_company",
]

_logger = logging.getLogger(__name__)


async def _delete_company_files(company_profile: CompanyProfile) -> None:
    """Delete all S3 files associated with a company profile (best-effort)."""
    storage = get_storage_provider()
    for key in [
        company_profile.logo_url,
        company_profile.agreement_signature_url,
        company_profile.contract_pdf_url,
    ]:
        if key:
            try:
                await storage.delete_file(key)
            except Exception:
                _logger.exception("Failed to delete storage file %s", key)


async def get_all_admin_emails(session: AsyncSession) -> list[str]:
    """Get email addresses of all active admin users."""
    result = await session.execute(
        select(User.email).where(  # pyright: ignore[reportArgumentType]
            User.role == UserRole.ADMIN,
            User.is_active == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def list_pending_companies(
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[PendingCompanyRead]:
    """One page of pending companies (inactive COMPANY users), newest first."""
    page_size = clamp_limit(limit)
    query = apply_cursor(
        select(User, CompanyProfile, ActivationToken)
        .join(CompanyProfile, User.id == CompanyProfile.user_id)
        .outerjoin(
            ActivationToken,
            (ActivationToken.user_id == User.id) & (ActivationToken.used == False),  # noqa: E712
        )
        .where(User.role == UserRole.COMPANY, User.is_active == False),  # noqa: E712
        sort_col=User.created_at,  # pyright: ignore[reportArgumentType]
        id_col=User.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
    )
    rows = list((await session.execute(query)).all())
    return build_cursor_page(
        rows,
        serializer=lambda row: PendingCompanyRead(
            user=UserRead.model_validate(row[0]),
            company_profile=CompanyProfileRead.model_validate(row[1]),
            invitation_sent=row[2] is not None,
        ),
        cursor_key=lambda row: (row[0].created_at, row[0].id),
        limit=page_size,
    )


async def reject_company(
    company_user_id: int,
    session: AsyncSession,
    *,
    actor_user_id: int | None = None,
    ip_address: str | None = None,
) -> None:
    """Reject a company registration by deleting the user and company profile.

    Raises:
        CompanyNotFoundError: If company user not found
        CompanyNotPendingError: If already approved or not a COMPANY user
    """
    user = await validate_company_user_pending(company_user_id, session)

    company_profile = user.company_profile

    _rejection_email = user.email
    _company_name_for_email = company_profile.name or ""
    _rejected_plain = (
        f"בקשת ההרשמה של '{_company_name_for_email}' נדחתה. "
        "אם לדעתכם מדובר בטעות, אנא צרו קשר עם support@rs-recruiting.com"
    )
    _rejection_html = build_rejection_html(_company_name_for_email)
    defer_after_commit(
        lambda: enqueue_email_task(
            to=_rejection_email,
            subject="בקשת ההרשמה נדחתה – RS Recruiting",
            body=_rejected_plain,
            html_body=_rejection_html,
        )
    )

    await _delete_company_files(company_profile)

    rejected_target_id = company_profile.id

    # CompanyProfile, ActivationToken, RefreshToken, PasswordResetToken all
    # cascade from user.id at the DB level — see migration
    # c4d2a8f1e9b7_fk_cascade_company_user_chain.
    await session.delete(user)
    await session.flush()

    await record_audit_event(
        session,
        actor_user_id=actor_user_id,
        action="company.reject",
        target_type="CompanyProfile",
        target_id=rejected_target_id,
        ip_address=ip_address,
    )


async def list_active_companies(
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[ActiveCompanyRead]:
    """One page of active companies, newest first.

    Includes both company users that have been approved (is_active=True) and
    admin-created profiles that have no user account yet (user_id=None).
    """
    page_size = clamp_limit(limit)
    query = apply_cursor(
        select(CompanyProfile, User)
        .outerjoin(User, CompanyProfile.user_id == User.id)  # pyright: ignore[reportArgumentType]
        .where(
            (CompanyProfile.user_id == None)  # noqa: E711 — orphan profiles (IS NULL)
            | (  # pyright: ignore[reportOperatorIssue]
                (User.role == UserRole.COMPANY) & (User.is_active == True)  # noqa: E712
            )
        ),
        sort_col=CompanyProfile.created_at,  # pyright: ignore[reportArgumentType]
        id_col=CompanyProfile.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
    )
    rows = list((await session.execute(query)).all())
    return build_cursor_page(
        rows,
        serializer=lambda row: ActiveCompanyRead(
            user=UserRead.model_validate(row[1]) if row[1] is not None else None,
            company_profile=CompanyProfileRead.model_validate(row[0]),
        ),
        cursor_key=lambda row: (row[0].created_at, row[0].id),
        limit=page_size,
    )


async def delete_active_company(
    company_user_id: int,
    session: AsyncSession,
    *,
    actor_user_id: int | None = None,
    ip_address: str | None = None,
) -> None:
    """Hard-delete a company. DB cascades through dependent rows.

    CompanyProfile, Job, Application, ActivationToken, RefreshToken, and
    PasswordResetToken all cascade from user.id / companyprofile.id at the
    DB level (migration c4d2a8f1e9b7).

    Raises:
        CompanyNotFoundError: If no COMPANY user with that ID exists
    """
    result = await session.execute(
        select(User, CompanyProfile)
        .join(CompanyProfile, User.id == CompanyProfile.user_id)  # pyright: ignore[reportArgumentType]
        .where(User.id == company_user_id, User.role == UserRole.COMPANY)
    )
    row = result.one_or_none()
    if not row:
        raise CompanyNotFoundError(f"Company user with ID {company_user_id} not found")
    user, cp = row
    cp_id = cp.id

    await _delete_company_files(cp)

    await session.delete(user)
    await session.flush()

    await record_audit_event(
        session,
        actor_user_id=actor_user_id,
        action="company.delete",
        target_type="CompanyProfile",
        target_id=cp_id,
        ip_address=ip_address,
    )
