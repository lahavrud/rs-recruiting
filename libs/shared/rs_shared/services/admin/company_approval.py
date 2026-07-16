"""Approval flow for pending company registrations.

Extracted from `admin_companies.py` to keep that module under the file size
limit. Imports remain backward-compatible: `admin_companies` re-exports
`approve_company` so existing call sites and tests are unaffected.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.infrastructure.security import hash_token
from rs_shared.core.services.storage import get_storage_provider
from rs_shared.core.tasks import queue_email
from rs_shared.models import ActivationToken
from rs_shared.schemas import CompanyProfileRead, UserRead
from rs_shared.services.admin._helpers import validate_company_user_pending
from rs_shared.services.utils.audit import record_audit_event
from rs_shared.services.utils.contract_pdf import generate_signed_contract
from rs_shared.templates.email import build_approval_html

_ACTIVATION_TTL_HOURS = 48
_logger = logging.getLogger(__name__)


async def approve_company(
    company_user_id: int,
    session: AsyncSession,
    *,
    actor_user_id: int | None = None,
    ip_address: str | None = None,
) -> dict:
    """Approve a pending company registration.

    Generates an activation token, builds the signed contract PDF, and emails
    the company an activation link with the PDF attached.  The account is NOT
    activated here — the company must click the link.

    Raises:
        CompanyNotFoundError: If company user not found
        CompanyNotPendingError: If already approved or not a COMPANY user
    """
    user = await validate_company_user_pending(company_user_id, session)

    company_profile = user.company_profile

    # Revoke any previous (unused, possibly expired) activation token before
    # issuing a new one. This allows re-approval after a token expires or
    # after the admin rejects and later changes their mind.
    stale_result = await session.execute(
        select(ActivationToken).where(
            ActivationToken.user_id == company_user_id,  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
            ActivationToken.used == False,  # noqa: E712
        )
    )
    stale = stale_result.scalar_one_or_none()
    if stale is not None:
        await session.delete(stale)
        await session.flush()

    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=_ACTIVATION_TTL_HOURS)
    activation = ActivationToken(
        token_hash=hash_token(raw_token),
        user_id=company_user_id,
        expires_at=expires_at,
    )
    session.add(activation)
    await session.flush()

    activation_url = f"{settings.frontend_base_url}/activate?token={raw_token}"

    # Generate signed contract PDF + upload + persist contract_pdf_url synchronously
    # so the approval state is atomic with the DB row. Only the email send (which
    # talks to SMTP and is the slow part) is deferred until after commit.
    pdf_bytes: bytes | None = None
    try:
        storage = get_storage_provider()
        if company_profile.agreement_signature_url:
            sig_bytes = await storage.download_file(
                company_profile.agreement_signature_url
            )
            signed_at = company_profile.agreement_signed_at or datetime.now(
                timezone.utc
            )
            pdf_bytes = await generate_signed_contract(
                company_name=company_profile.name or "",
                company_id=company_profile.company_id or "",
                address=company_profile.address or "",
                signed_at=signed_at,
                company_signature_png_bytes=sig_bytes,
            )
            if pdf_bytes:
                pdf_key = await storage.upload_file(
                    pdf_bytes,
                    f"contracts/{company_profile.company_id}_contract.pdf",
                    "application/pdf",
                )
                company_profile.contract_pdf_url = pdf_key
                await session.flush()
    except Exception:
        # PDF generation/upload is best-effort — approval proceeds without it
        _logger.exception(
            "Failed to generate/store signed contract for company %s", company_user_id
        )

    company_name = company_profile.name or ""
    plain = (
        f"שלום,\n\n"
        f"בקשת ההרשמה של {company_name} אושרה.\n\n"
        f"לחצו על הקישור להפעלת החשבון:\n{activation_url}\n\n"
        "בברכה,\nצוות RS Recruiting"
    )
    await queue_email(
        session,
        to=user.email,
        subject="בקשת ההרשמה שלכם אושרה – RS Recruiting",
        body=plain,
        html_body=build_approval_html(company_name, activation_url),
        attachments=(
            [("חוזה-RS.pdf", pdf_bytes, "application/pdf")] if pdf_bytes else None
        ),
    )

    await record_audit_event(
        session,
        actor_user_id=actor_user_id,
        action="company.approve",
        target_type="CompanyProfile",
        target_id=company_profile.id,
        ip_address=ip_address,
    )

    return {
        "user": UserRead.model_validate(user),
        "company_profile": CompanyProfileRead.model_validate(company_profile),
    }
