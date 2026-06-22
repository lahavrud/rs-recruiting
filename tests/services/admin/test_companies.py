"""Unit tests for admin_companies service layer."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import get_password_hash
from src.enums import UserRole
from src.models import (
    ActivationToken,
    Application,
    CandidateProfile,
    CompanyProfile,
    Job,
    PasswordResetToken,
    RefreshToken,
    User,
)
from src.schemas import CompanyProfileAdminCreate, CompanyProfileCreate, UserCreate
from src.services.admin.companies import (
    delete_active_company,
    get_all_admin_emails,
    list_active_companies,
    list_pending_companies,
    reject_company,
)
from src.services.admin.company_profiles import admin_create_company
from src.services.auth.registration import (
    CompanyRegistrationData,
    register_company_user,
)
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
        data,
        session,
        _LOGO,
        "logo.png",
        CompanyRegistrationData(
            logo_content_type="image/png", agreement_signature=_SIG
        ),
    )
    await session.commit()
    return result.user


# ── get_all_admin_emails ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_all_admin_emails(session: AsyncSession):
    admin1 = User(
        email="admin1@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    admin2 = User(
        email="admin2@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    inactive_admin = User(
        email="admin3@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=False,
    )
    company = User(
        email="company@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add_all([admin1, admin2, inactive_admin, company])
    await session.commit()

    emails = await get_all_admin_emails(session)
    assert set(emails) == {"admin1@example.com", "admin2@example.com"}


# ── list_pending_companies ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_pending_companies_empty(session: AsyncSession):
    page = await list_pending_companies(session)
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.asyncio
@patch("src.services.auth.registration.enqueue_email_task")
async def test_list_pending_companies(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    await _register(_company_create("p1@example.com", "Company 1"), session)
    await _register(_company_create("p2@example.com", "Company 2"), session)

    # Active company should not appear
    user = await _register(_company_create("active@example.com", "Active Co"), session)
    res = await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
    res.scalar_one().is_active = True
    await session.commit()

    page = await list_pending_companies(session)
    assert len(page.items) == 2
    emails = {c.user.email for c in page.items}
    assert emails == {"p1@example.com", "p2@example.com"}
    assert all(not c.user.is_active for c in page.items)
    assert page.next_cursor is None


@pytest.mark.asyncio
@patch("src.services.auth.registration.enqueue_email_task")
async def test_list_pending_companies_paginates(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    for i in range(5):
        await _register(
            _company_create(f"pend{i}@example.com", f"Pending {i}"), session
        )

    seen: list[str] = []
    cursor: str | None = None
    while True:
        page = await list_pending_companies(session, cursor=cursor, limit=2)
        seen.extend(item.user.email for item in page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor

    assert len(seen) == 5
    assert len(set(seen)) == 5


# ── reject_company ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("src.services.admin.companies.enqueue_email_task")
async def test_reject_company_success(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    user = await _register(_company_create("reject@example.com", "Reject Co"), session)
    user_id = user.id

    cp_res = await session.execute(
        select(CompanyProfile).where(CompanyProfile.user_id == user_id)  # pyright: ignore[reportArgumentType]
    )
    cp_id = cp_res.scalar_one().id

    await reject_company(user_id, session)
    await session.commit()

    assert (
        await session.execute(select(User).where(User.id == user_id))  # pyright: ignore[reportArgumentType]
    ).scalar_one_or_none() is None
    assert (
        await session.execute(
            select(CompanyProfile).where(CompanyProfile.id == cp_id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
@patch("src.services.admin.companies.enqueue_email_task")
@patch("src.services.admin.companies.get_storage_provider")
async def test_reject_company_deletes_s3_files(
    mock_storage, mock_email, session: AsyncSession
):
    """S3 files (logo + signature) are deleted when a company is rejected."""
    mock_email.return_value = "job-id"
    mock_storage.return_value.delete_file = AsyncMock(return_value=True)
    user = await _register(
        _company_create("reject2@example.com", "Reject2 Co"), session
    )

    await reject_company(user.id, session)
    await session.commit()

    assert mock_storage.return_value.delete_file.call_count >= 1


@pytest.mark.asyncio
async def test_reject_company_not_found(session: AsyncSession):
    with pytest.raises(CompanyNotFoundError):
        await reject_company(99999, session)


@pytest.mark.asyncio
@patch("src.services.auth.registration.enqueue_email_task")
async def test_reject_company_already_approved(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    user = await _register(
        _company_create("rejectactive@example.com", "Active Co"), session
    )
    db_user = (
        await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
    ).scalar_one()
    db_user.is_active = True
    await session.commit()

    with pytest.raises(CompanyNotPendingError):
        await reject_company(user.id, session)


@pytest.mark.asyncio
async def test_reject_company_wrong_role(session: AsyncSession):
    admin = User(
        email="rejectadmin@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=False,
    )
    session.add(admin)
    await session.commit()

    with pytest.raises(CompanyNotPendingError):
        await reject_company(admin.id, session)


# ── list_active_companies ─────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("src.services.auth.registration.enqueue_email_task")
async def test_list_active_companies_empty(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    # Pending company should not appear
    await _register(_company_create("pending@example.com", "Pending Co"), session)
    page = await list_active_companies(session)
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.asyncio
@patch("src.services.auth.registration.enqueue_email_task")
async def test_list_active_companies(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    for email, name in [("a@example.com", "A Co"), ("b@example.com", "B Co")]:
        user = await _register(_company_create(email, name), session)
        db_user = (
            await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
        ).scalar_one()
        db_user.is_active = True
    await session.commit()

    page = await list_active_companies(session)
    assert len(page.items) == 2
    emails = {c.user.email for c in page.items}
    assert emails == {"a@example.com", "b@example.com"}
    assert all(c.user.is_active for c in page.items)


@pytest.mark.asyncio
@patch("src.services.auth.registration.enqueue_email_task")
async def test_list_active_companies_paginates(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    for i in range(5):
        user = await _register(
            _company_create(f"act{i}@example.com", f"Active {i}"), session
        )
        db_user = (
            await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
        ).scalar_one()
        db_user.is_active = True
    await session.commit()

    seen: list[str] = []
    cursor: str | None = None
    while True:
        page = await list_active_companies(session, cursor=cursor, limit=2)
        seen.extend(item.user.email for item in page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor

    assert len(seen) == 5
    assert len(set(seen)) == 5


@pytest.mark.asyncio
async def test_list_active_companies_includes_admin_created_profiles(
    session: AsyncSession,
):
    """Profiles created directly by admins (user_id=None) appear in the active list.

    Regression test for the transaction-boundary bug where admin-created profiles
    were persisted to the DB but invisible in every admin list view, because the
    query required an INNER JOIN with a user row.
    """
    payload = CompanyProfileAdminCreate(
        name="ללא חשבון",
        company_id="111222333",
        address="רח' כלשהי 1",
        contact_email="lelo-heshbon@example.com",
        contact_first_name="אורי",
        contact_last_name="ישיר",
        contact_mobile_phone="0501234567",
    )
    await admin_create_company(payload, session)
    await session.commit()

    page = await list_active_companies(session)

    assert len(page.items) == 1
    item = page.items[0]
    assert item.user is None
    assert item.company_profile.name == "ללא חשבון"
    assert item.company_profile.user_id is None


@pytest.mark.asyncio
@patch("src.services.auth.registration.enqueue_email_task")
async def test_delete_active_company_with_activation_and_refresh_tokens(
    mock_email, session: AsyncSession
):
    """delete_active_company removes ActivationToken + RefreshToken rows before
    deleting the user, preventing FK constraint violations on fully-activated
    company accounts.
    """
    mock_email.return_value = "job-id"
    user = await _register(_company_create("fk@example.com", "FK Co"), session)
    user_id = user.id

    from datetime import datetime, timezone

    # Simulate an activation token (as created by the approval flow).
    act_token = ActivationToken(
        token_hash="fake-act-token-hash",
        user_id=user_id,
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        used=True,
    )
    # Simulate a refresh token (as stored after the company logs in).
    ref_token = RefreshToken(
        token_hash="fake-hash",
        user_id=user_id,
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    session.add(act_token)
    session.add(ref_token)
    await session.commit()

    await delete_active_company(user_id, session)
    await session.commit()

    result = await session.execute(
        select(User).where(User.id == user_id)  # pyright: ignore[reportArgumentType]
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
@patch("src.services.auth.registration.enqueue_email_task")
async def test_delete_active_company_with_password_reset_token(
    mock_email, session: AsyncSession
):
    """Regression: PasswordResetToken (added in e7f3a2b1c8d4) FK-references
    user.id. Deleting a company that ever requested a password reset used to
    raise a FK violation. The CASCADE migration c4d2a8f1e9b7 fixed it.
    """
    mock_email.return_value = "job-id"
    user = await _register(
        _company_create("pwreset@example.com", "PwReset Co"), session
    )
    user_id = user.id

    from datetime import datetime, timezone

    reset_token = PasswordResetToken(
        token_hash="fake-reset-hash",
        user_id=user_id,
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        used=False,
    )
    session.add(reset_token)
    await session.commit()

    await delete_active_company(user_id, session)
    await session.commit()

    assert (
        await session.execute(select(User).where(User.id == user_id))  # pyright: ignore[reportArgumentType]
    ).scalar_one_or_none() is None
    assert (
        await session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user_id  # type: ignore[arg-type]
            )
        )
    ).scalar_one_or_none() is None


# ── delete_active_company ─────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("src.services.auth.registration.enqueue_email_task")
@patch("src.services.admin.companies.get_storage_provider")
async def test_delete_active_company_deletes_s3_files(
    mock_storage, mock_email, session: AsyncSession
):
    """S3 files (logo + signature) are deleted when a company is hard-deleted."""
    mock_email.return_value = "job-id"
    mock_storage.return_value.delete_file = AsyncMock(return_value=True)
    user = await _register(
        _company_create("delfiles@example.com", "DelFiles Co"), session
    )
    db_user = (
        await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
    ).scalar_one()
    db_user.is_active = True
    await session.commit()

    await delete_active_company(user.id, session)
    await session.commit()

    assert mock_storage.return_value.delete_file.call_count >= 1


@pytest.mark.asyncio
@patch("src.services.auth.registration.enqueue_email_task")
async def test_delete_active_company_no_jobs(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    user = await _register(_company_create("del@example.com", "Del Co"), session)
    db_user = (
        await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
    ).scalar_one()
    db_user.is_active = True
    await session.commit()
    user_id = user.id

    await delete_active_company(user_id, session)
    await session.commit()

    assert (
        await session.execute(select(User).where(User.id == user_id))  # pyright: ignore[reportArgumentType]
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
@patch("src.services.auth.registration.enqueue_email_task")
async def test_delete_active_company_cascades_jobs_and_applications(
    mock_email, session: AsyncSession
):
    mock_email.return_value = "job-id"
    user = await _register(
        _company_create("cascade@example.com", "Cascade Co"), session
    )
    db_user = (
        await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
    ).scalar_one()
    db_user.is_active = True
    await session.flush()

    cp = (
        await session.execute(
            select(CompanyProfile).where(CompanyProfile.user_id == user.id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one()

    job = Job(
        title="Engineer",
        short_description="Short blurb for testing.",
        description="Desc",
        requirements=[{"text": "Python"}, {"text": "Req 2"}, {"text": "Req 3"}],
        location="TLV",
        company_id=cp.id,
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job)
    await session.flush()

    candidate = CandidateProfile(
        full_name="Test Candidate",
        email="cand@example.com",
        phone="050-000-0000",
    )
    session.add(candidate)
    await session.flush()

    app = Application(job_id=job.id, candidate_id=candidate.id)
    session.add(app)
    await session.commit()

    job_id = job.id
    app_id = app.id
    user_id = user.id

    await delete_active_company(user_id, session)
    await session.commit()

    assert (
        await session.execute(select(User).where(User.id == user_id))  # pyright: ignore[reportArgumentType]
    ).scalar_one_or_none() is None
    assert (
        await session.execute(select(Job).where(Job.id == job_id))  # pyright: ignore[reportArgumentType]
    ).scalar_one_or_none() is None
    assert (
        await session.execute(
            select(Application).where(Application.id == app_id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_active_company_not_found(session: AsyncSession):
    with pytest.raises(CompanyNotFoundError):
        await delete_active_company(99999, session)
