"""Company-registration service.

Carved out of `src/services/auth.py` so that file stays under the
service-layer line cap. Keeps the registration flow — signature decode,
admin notification email, and the `register_company_user` orchestrator
— co-located while the rest of `auth.py` handles login, lockout, and
token lifecycle.
"""

import base64
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import get_password_hash
from src.core.infrastructure.transactions import defer_after_commit
from src.core.services.file_validation import is_valid_image_magic_bytes
from src.core.services.storage import get_storage_provider
from src.core.tasks import enqueue_email_task
from src.core.utils import mask_email
from src.enums import UserRole
from src.models import CompanyProfile, User
from src.schemas import CompanyProfileRead, UserCreate, UserRead, UserWithCompanyRead
from src.services.admin.companies import get_all_admin_emails
from src.services.exceptions import EmailAlreadyExistsError
from src.services.utils.audit import record_audit_event
from src.services.utils.legal import (
    CURRENT_PRIVACY_POLICY_VERSION,
    CURRENT_TERMS_OF_SERVICE_VERSION,
)
from src.templates.email import build_new_registration_html

logger = logging.getLogger(__name__)

_ALLOWED_LOGO_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_LOGO_SIZE = 2 * 1024 * 1024  # 2 MB
_MAX_SIGNATURE_SIZE = 2 * 1024 * 1024  # 2 MB decoded


def _decode_signature(agreement_signature: str) -> bytes:
    if not agreement_signature.strip():
        raise ValueError("Agreement signature is required")
    try:
        sig_bytes = base64.b64decode(agreement_signature, validate=True)
    except Exception as exc:
        raise ValueError("Invalid signature data") from exc
    if not sig_bytes:
        raise ValueError("Agreement signature is required")
    if len(sig_bytes) > _MAX_SIGNATURE_SIZE:
        raise ValueError("Signature image exceeds maximum allowed size")
    if not sig_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Signature must be a PNG image")
    return sig_bytes


async def _notify_admins_new_registration(
    profile: CompanyProfile,
    email: str,
    sig_bytes: bytes,
    signed_at: datetime,
    admin_emails: list[str],
) -> None:
    from src.core.infrastructure.config import settings

    admin_url = f"{settings.frontend_base_url}/login?redirect=/admin/companies"
    html = build_new_registration_html(
        company_name=profile.name or "",
        company_id=profile.company_id or "—",
        address=profile.address or "—",
        contact_name=f"{profile.contact_first_name} {profile.contact_last_name}",
        email=email,
        mobile=profile.contact_mobile_phone or "—",
        admin_url=admin_url,
    )
    pdf_bytes: bytes | None = None
    try:
        from src.services.utils.contract_pdf import generate_signed_contract

        pdf_bytes = await generate_signed_contract(
            company_name=profile.name or "",
            company_id=profile.company_id or "",
            address=profile.address or "",
            signed_at=signed_at,
            company_signature_png_bytes=sig_bytes,
        )
    except Exception:
        logger.exception("Failed to generate contract PDF for %s", mask_email(email))
    attachments = [("חוזה-RS.pdf", pdf_bytes, "application/pdf")] if pdf_bytes else None
    await enqueue_email_task(
        to=admin_emails,
        subject="בקשת הרשמה חדשה ממתינה לאישור – RS Recruiting",
        body=f"חברה חדשה '{profile.name}' נרשמה וממתינה לאישור.\nכתובת: {admin_url}",
        html_body=html,
        attachments=attachments,
    )


async def register_company_user(
    user_data: UserCreate,
    session: AsyncSession,
    logo_content: bytes,
    logo_filename: str,
    logo_content_type: str | None = None,
    agreement_signature: str = "",
    privacy_accepted: bool = False,
    terms_accepted: bool = False,
    acceptance_ip: str | None = None,
    acceptance_user_agent: str | None = None,
) -> UserWithCompanyRead:
    """Register a new company user with associated company profile."""
    if logo_content_type and logo_content_type not in _ALLOWED_LOGO_TYPES:
        raise ValueError("Logo must be an image file (JPEG, PNG, GIF, or WebP)")
    if len(logo_content) > _MAX_LOGO_SIZE:
        raise ValueError("Logo file size exceeds 5 MB limit")
    if logo_content_type and not is_valid_image_magic_bytes(
        logo_content, logo_content_type
    ):
        raise ValueError("Logo file content does not match the declared image type")

    sig_bytes = _decode_signature(agreement_signature)

    normalized_email = user_data.email.lower().strip()
    result = await session.execute(
        select(User).where(User.email == normalized_email)  # pyright: ignore[reportArgumentType]
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        logger.warning(
            "registration_email_exists",
            extra={"email_prefix": normalized_email[:2] + "***"},
        )
        raise EmailAlreadyExistsError(normalized_email)

    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=normalized_email,
        hashed_password=hashed_password,
        role=UserRole.COMPANY,
        is_active=False,
    )
    session.add(new_user)
    # Flush User first so any constraint violation (e.g. duplicate email race)
    # raises before any S3 bytes are written — no orphan risk on that path.
    await session.flush()

    storage = get_storage_provider()
    logo_identifier = await storage.upload_file(
        logo_content, f"logos/{logo_filename}", logo_content_type
    )
    sig_filename = f"{user_data.company_profile.company_id}_agreement.png"
    sig_identifier: str | None = None
    try:
        sig_identifier = await storage.upload_file(
            sig_bytes, f"signatures/{sig_filename}", "image/png"
        )
    except Exception:
        # Clean up the already-uploaded logo before re-raising so the
        # transaction rollback leaves no orphaned S3 objects.
        try:
            await storage.delete_file(logo_identifier)
        except Exception:
            logger.exception("Failed to clean up logo after signature upload error")
        raise

    profile = user_data.company_profile
    now = datetime.now(timezone.utc)
    new_company_profile = CompanyProfile(
        user_id=new_user.id,
        name=profile.name,
        logo_url=logo_identifier,
        company_id=profile.company_id,
        address=profile.address,
        contact_email=user_data.email,
        contact_first_name=profile.contact_first_name,
        contact_last_name=profile.contact_last_name,
        contact_mobile_phone=profile.contact_mobile_phone,
        contact_landline_phone=profile.contact_landline_phone,
        agreement_signature_url=sig_identifier,
        agreement_signed_at=now,
        privacy_accepted_at=now if privacy_accepted else None,
        privacy_policy_version=(
            CURRENT_PRIVACY_POLICY_VERSION if privacy_accepted else None
        ),
        terms_accepted_at=now if terms_accepted else None,
        terms_version=(CURRENT_TERMS_OF_SERVICE_VERSION if terms_accepted else None),
        acceptance_ip=acceptance_ip,
        acceptance_user_agent=acceptance_user_agent,
    )

    # Wrap remaining DB work so any unexpected flush/audit failure triggers
    # cleanup of both S3 files before propagating.
    try:
        session.add(new_company_profile)
        await session.flush()

        if privacy_accepted:
            await record_audit_event(
                session,
                actor_user_id=new_user.id,
                action="company.privacy_accept",
                target_type="CompanyProfile",
                target_id=new_company_profile.id,  # type: ignore[arg-type]  # model id is int | None pre-flush; always set once persisted
                detail=f"policy_version={CURRENT_PRIVACY_POLICY_VERSION}",
                ip_address=acceptance_ip,
            )
        if terms_accepted:
            await record_audit_event(
                session,
                actor_user_id=new_user.id,
                action="company.terms_accept",
                target_type="CompanyProfile",
                target_id=new_company_profile.id,  # type: ignore[arg-type]  # model id is int | None pre-flush; always set once persisted
                detail=f"terms_version={CURRENT_TERMS_OF_SERVICE_VERSION}",
                ip_address=acceptance_ip,
            )
        await record_audit_event(
            session,
            actor_user_id=new_user.id,
            action="company.contract_sign",
            target_type="CompanyProfile",
            target_id=new_company_profile.id,  # type: ignore[arg-type]  # model id is int | None pre-flush; always set once persisted
            detail=f"signature_url={sig_identifier}",
            ip_address=acceptance_ip,
        )
    except Exception:
        for key in [logo_identifier, sig_identifier]:
            if key:
                try:
                    await storage.delete_file(key)
                except Exception:
                    logger.exception(
                        "Failed to clean up S3 file %s after DB error", key
                    )
        raise

    admin_emails = await get_all_admin_emails(session)
    if admin_emails:
        defer_after_commit(
            lambda: _notify_admins_new_registration(
                new_company_profile, new_user.email, sig_bytes, now, admin_emails
            )
        )

    return UserWithCompanyRead(
        user=UserRead.model_validate(new_user),
        company_profile=CompanyProfileRead.model_validate(new_company_profile),
    )
