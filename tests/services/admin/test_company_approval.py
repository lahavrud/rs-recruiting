"""Unit tests for the company approval service.

Moved here when `approve_company` was extracted from `admin_companies` into
its own module.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import get_password_hash
from src.enums import UserRole
from src.models import CompanyProfile, User
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.admin.company_approval import approve_company
from src.services.auth.registration import register_company_user
from src.services.exceptions import CompanyNotFoundError, CompanyNotPendingError
from tests.conftest import FAKE_LOGO as _LOGO
from tests.conftest import FAKE_SIG_B64 as _SIG


def _company_create(email: str, name: str) -> UserCreate:
    return UserCreate(
        email=email,
        password="SecurePass1!",
        company_profile=CompanyProfileCreate(
            name=name,
            company_id="123456789",
            address="רח׳ הדוגמה 1, תל אביב",
            contact_first_name="ישראל",
            contact_last_name="ישראלי",
            contact_mobile_phone="0501234567",
        ),
    )


async def _register(data: UserCreate, session: AsyncSession) -> User:
    result = await register_company_user(
        data, session, _LOGO, "logo.png", "image/png", _SIG
    )
    await session.commit()
    return result.user


@pytest.mark.asyncio
@patch("src.services.admin.company_approval.enqueue_email_task")
@patch("src.services.admin.company_approval.generate_signed_contract")
@patch("src.services.admin.company_approval.get_storage_provider")
async def test_approve_company_uploads_contract(
    mock_storage, mock_pdf, mock_email, session: AsyncSession
):
    mock_email.return_value = "job-id"
    mock_pdf.return_value = b"%PDF-fake"
    mock_storage.return_value.download_file = AsyncMock(return_value=b"fake-sig-bytes")
    mock_storage.return_value.upload_file = AsyncMock(return_value="contract-key.pdf")

    user = await _register(
        _company_create("approve@example.com", "Approve Co"), session
    )
    assert not user.is_active

    await approve_company(user.id, session)
    await session.commit()

    mock_storage.return_value.upload_file.assert_called_once()


@pytest.mark.asyncio
@patch("src.services.admin.company_approval.enqueue_email_task")
@patch("src.services.admin.company_approval.generate_signed_contract")
@patch("src.services.admin.company_approval.get_storage_provider")
async def test_approve_company_does_not_auto_activate_user(
    mock_storage, mock_pdf, mock_email, session: AsyncSession
):
    mock_email.return_value = "job-id"
    mock_pdf.return_value = b"%PDF-fake"
    mock_storage.return_value.download_file = AsyncMock(return_value=b"fake-sig-bytes")
    mock_storage.return_value.upload_file = AsyncMock(return_value="contract-key.pdf")

    user = await _register(
        _company_create("approve@example.com", "Approve Co"), session
    )
    assert not user.is_active

    result = await approve_company(user.id, session)
    await session.commit()

    assert result["user"].is_active is False
    db_user = (
        await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
    ).scalar_one()
    assert db_user.is_active is False


@pytest.mark.asyncio
@patch("src.services.admin.company_approval.enqueue_email_task")
@patch("src.services.admin.company_approval.generate_signed_contract")
@patch("src.services.admin.company_approval.get_storage_provider")
async def test_approve_company_updates_contract_pdf_url(
    mock_storage, mock_pdf, mock_email, session: AsyncSession
):
    mock_email.return_value = "job-id"
    mock_pdf.return_value = b"%PDF-fake"
    mock_storage.return_value.download_file = AsyncMock(return_value=b"fake-sig-bytes")
    mock_storage.return_value.upload_file = AsyncMock(return_value="contract-key.pdf")

    user = await _register(
        _company_create("approve@example.com", "Approve Co"), session
    )
    assert not user.is_active

    await approve_company(user.id, session)
    await session.commit()

    cp = (
        await session.execute(
            select(CompanyProfile).where(CompanyProfile.user_id == user.id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one()
    assert cp.contract_pdf_url == "contract-key.pdf"


@pytest.mark.asyncio
async def test_approve_company_not_found(session: AsyncSession):
    with pytest.raises(CompanyNotFoundError):
        await approve_company(99999, session)


@pytest.mark.asyncio
@patch("src.services.auth.registration.enqueue_email_task")
async def test_approve_company_already_approved(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    user = await _register(
        _company_create("already@example.com", "Already Co"), session
    )
    db_user = (
        await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
    ).scalar_one()
    db_user.is_active = True
    await session.commit()

    with pytest.raises(CompanyNotPendingError):
        await approve_company(user.id, session)


@pytest.mark.asyncio
async def test_approve_company_wrong_role(session: AsyncSession):
    admin = User(
        email="wrongrole@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=False,
    )
    session.add(admin)
    await session.commit()

    with pytest.raises(CompanyNotPendingError):
        await approve_company(admin.id, session)


@pytest.mark.asyncio
@patch("src.services.admin.company_approval.enqueue_email_task")
@patch("src.services.admin.company_approval.generate_signed_contract")
@patch("src.services.admin.company_approval.get_storage_provider")
async def test_approve_company_writes_audit_row(
    mock_storage, mock_pdf, mock_email, session: AsyncSession
):
    """The approve flow must record a `company.approve` audit event."""
    from src.models import AuditLog

    mock_email.return_value = "job-id"
    mock_pdf.return_value = None
    mock_storage.return_value.download_file = AsyncMock(return_value=b"sig")

    user = await _register(_company_create("audit@example.com", "Audit Co"), session)
    await approve_company(user.id, session, actor_user_id=42, ip_address="10.0.0.1")
    await session.commit()

    rows = (await session.execute(select(AuditLog))).scalars().all()
    matching = [r for r in rows if r.action == "company.approve"]
    assert len(matching) == 1
    assert matching[0].actor_user_id == 42
    assert matching[0].ip_address == "10.0.0.1"
    assert matching[0].target_type == "CompanyProfile"
