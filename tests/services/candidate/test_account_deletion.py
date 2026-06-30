"""Service-level tests for candidate GDPR account deletion (#611)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import get_password_hash, hash_token
from rs_shared.enums import ApplicationStatus, UserRole
from rs_shared.models import (
    AccountDeletionToken,
    Application,
    AuditLog,
    CandidateProfile,
    Job,
    User,
)
from rs_shared.services.candidate.account_deletion import (
    check_deletion_token,
    confirm_deletion,
    request_account_deletion,
)
from rs_shared.services.exceptions import InvalidAccountDeletionTokenError

_NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


async def _make_user(
    session: AsyncSession,
    *,
    email: str = "cand@test.com",
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash("Secret1!"),  # pragma: allowlist secret
        role=UserRole.CANDIDATE,
        is_active=is_active,
    )
    session.add(user)
    await session.flush()
    return user


async def _make_profile(
    session: AsyncSession,
    *,
    user: User | None = None,
    email: str = "cand@test.com",
) -> CandidateProfile:
    profile = CandidateProfile(
        user_id=user.id if user else None,
        full_name="Test Candidate",
        email=email,
        phone="050-0000001",
        linkedin_url="https://linkedin.com/in/test",
    )
    session.add(profile)
    await session.flush()
    return profile


async def _make_job(session: AsyncSession, company_with_user) -> Job:
    company, _ = company_with_user
    from rs_shared.enums import JobStatus

    job = Job(
        title="Dev",
        company_id=company.id,
        status=JobStatus.OPEN,
        location="TLV",
        description="x",
        requirements="y",
    )
    session.add(job)
    await session.flush()
    return job


async def _make_application(
    session: AsyncSession,
    *,
    profile: CandidateProfile,
    job: Job,
    resume_path: str | None = None,
) -> Application:
    app = Application(
        candidate_id=profile.id,
        job_id=job.id,
        status=ApplicationStatus.NEW,
        resume_path=resume_path,
    )
    session.add(app)
    await session.flush()
    return app


def _mock_storage(fail_delete: bool = False) -> MagicMock:
    storage = MagicMock()
    if fail_delete:
        storage.delete_file = AsyncMock(side_effect=Exception("S3 error"))
    else:
        storage.delete_file = AsyncMock(return_value=True)
    return storage


def _make_deletion_token_row(
    profile: CandidateProfile,
    *,
    used: bool = False,
    expires_at: datetime | None = None,
) -> tuple[str, AccountDeletionToken]:
    raw = secrets.token_urlsafe(32)
    record = AccountDeletionToken(
        token_hash=hash_token(raw),
        candidate_profile_id=profile.id,
        expires_at=expires_at or (_NOW + timedelta(hours=24)),
        used=used,
    )
    return raw, record


# ---------------------------------------------------------------------------
# request_account_deletion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_deletion_sends_email_for_known_email(session):
    user = await _make_user(session, email="known@test.com")
    await _make_profile(session, user=user, email="known@test.com")
    await session.flush()

    with patch(
        "rs_shared.services.candidate.account_deletion.defer_after_commit"
    ) as mock_defer:
        await request_account_deletion("known@test.com", session)

    mock_defer.assert_called_once()
    result = await session.execute(
        select(AccountDeletionToken).where(
            AccountDeletionToken.candidate_profile_id  # type: ignore[arg-type]
            == (
                await session.execute(
                    select(CandidateProfile).where(
                        CandidateProfile.email == "known@test.com"  # type: ignore[arg-type]
                    )
                )
            )
            .scalar_one()
            .id
        )
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_request_deletion_silent_for_unknown_email(session):
    with patch(
        "rs_shared.services.candidate.account_deletion.defer_after_commit"
    ) as mock_defer:
        await request_account_deletion("nobody@test.com", session)

    mock_defer.assert_not_called()


@pytest.mark.asyncio
async def test_request_deletion_silent_for_already_deleted_profile(session):
    profile = await _make_profile(session, email="gone@test.com")
    profile.deleted_at = _NOW - timedelta(days=1)
    await session.flush()

    with patch(
        "rs_shared.services.candidate.account_deletion.defer_after_commit"
    ) as mock_defer:
        await request_account_deletion("gone@test.com", session)

    mock_defer.assert_not_called()


@pytest.mark.asyncio
async def test_request_deletion_rate_limit_blocks_after_3(session):
    profile = await _make_profile(session, email="rl@test.com")
    # Seed 3 existing tokens within the last 24h.
    for _ in range(3):
        _, rec = _make_deletion_token_row(profile)
        session.add(rec)
    await session.flush()

    with patch(
        "rs_shared.services.candidate.account_deletion.defer_after_commit"
    ) as mock_defer:
        await request_account_deletion("rl@test.com", session)

    mock_defer.assert_not_called()


@pytest.mark.asyncio
async def test_request_deletion_writes_audit_event(session):
    user = await _make_user(session, email="audit@test.com")
    await _make_profile(session, user=user, email="audit@test.com")
    await session.flush()

    with patch("rs_shared.services.candidate.account_deletion.defer_after_commit"):
        await request_account_deletion("audit@test.com", session)

    audit_rows = list(
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "account_deletion_requested"  # type: ignore[arg-type]
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].target_type == "candidateprofile"


# ---------------------------------------------------------------------------
# check_deletion_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_deletion_token_valid(session):
    profile = await _make_profile(session, email="chk@test.com")
    raw, rec = _make_deletion_token_row(profile)
    session.add(rec)
    await session.flush()

    # Should not raise.
    await check_deletion_token(raw, session)


@pytest.mark.asyncio
async def test_check_deletion_token_expired_raises(session):
    profile = await _make_profile(session, email="exp_chk@test.com")
    raw, rec = _make_deletion_token_row(profile, expires_at=_NOW - timedelta(hours=1))
    session.add(rec)
    await session.flush()

    with pytest.raises(InvalidAccountDeletionTokenError):
        await check_deletion_token(raw, session)


@pytest.mark.asyncio
async def test_check_deletion_token_used_raises(session):
    profile = await _make_profile(session, email="used_chk@test.com")
    raw, rec = _make_deletion_token_row(profile, used=True)
    session.add(rec)
    await session.flush()

    with pytest.raises(InvalidAccountDeletionTokenError):
        await check_deletion_token(raw, session)


@pytest.mark.asyncio
async def test_check_deletion_token_unknown_raises(session):
    with pytest.raises(InvalidAccountDeletionTokenError):
        await check_deletion_token("completely-invalid-token", session)


# ---------------------------------------------------------------------------
# confirm_deletion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_deletion_tombstones_profile(session, company_with_user):
    user = await _make_user(session, email="del@test.com")
    profile = await _make_profile(session, user=user, email="del@test.com")
    profile_id = profile.id
    raw, rec = _make_deletion_token_row(profile)
    session.add(rec)
    await session.flush()

    storage = _mock_storage()
    await confirm_deletion(raw, session, storage=storage)

    refreshed = await session.get(CandidateProfile, profile_id)
    assert refreshed is not None
    assert refreshed.deleted_at is not None
    assert refreshed.full_name == "[מחוק]"
    assert refreshed.email == f"deleted-{profile_id}@deleted"
    assert refreshed.phone is None
    assert refreshed.linkedin_url is None


@pytest.mark.asyncio
async def test_confirm_deletion_hard_deletes_user(session):
    user = await _make_user(session, email="userdel@test.com")
    profile = await _make_profile(session, user=user, email="userdel@test.com")
    user_id = user.id
    raw, rec = _make_deletion_token_row(profile)
    session.add(rec)
    await session.flush()

    storage = _mock_storage()
    await confirm_deletion(raw, session, storage=storage)
    await session.flush()

    assert await session.get(User, user_id) is None


@pytest.mark.asyncio
async def test_confirm_deletion_nulls_application_resume_paths(
    session, company_with_user
):
    user = await _make_user(session, email="appdel@test.com")
    profile = await _make_profile(session, user=user, email="appdel@test.com")
    job = await _make_job(session, company_with_user)
    app = await _make_application(
        session, profile=profile, job=job, resume_path="resumes/cv.pdf"
    )
    app_id = app.id
    raw, rec = _make_deletion_token_row(profile)
    session.add(rec)
    await session.flush()

    storage = _mock_storage()
    await confirm_deletion(raw, session, storage=storage)

    refreshed_app = await session.get(Application, app_id)
    assert refreshed_app is not None
    assert refreshed_app.resume_path is None


@pytest.mark.asyncio
async def test_confirm_deletion_deletes_resume_from_storage(session):
    user = await _make_user(session, email="stordel@test.com")
    profile = await _make_profile(session, user=user, email="stordel@test.com")
    profile.resume_path = "resumes/my-cv.pdf"
    await session.flush()
    raw, rec = _make_deletion_token_row(profile)
    session.add(rec)
    await session.flush()

    storage = _mock_storage()
    await confirm_deletion(raw, session, storage=storage)

    storage.delete_file.assert_awaited_once_with("resumes/my-cv.pdf")


@pytest.mark.asyncio
async def test_confirm_deletion_succeeds_on_storage_failure(session):
    """Storage failure must not abort the deletion (best-effort)."""
    user = await _make_user(session, email="storefail@test.com")
    profile = await _make_profile(session, user=user, email="storefail@test.com")
    profile.resume_path = "resumes/cv.pdf"
    profile_id = profile.id
    await session.flush()
    raw, rec = _make_deletion_token_row(profile)
    session.add(rec)
    await session.flush()

    storage = _mock_storage(fail_delete=True)
    await confirm_deletion(raw, session, storage=storage)

    refreshed = await session.get(CandidateProfile, profile_id)
    assert refreshed is not None
    assert refreshed.deleted_at is not None


@pytest.mark.asyncio
async def test_confirm_deletion_marks_token_used(session):
    user = await _make_user(session, email="tokused@test.com")
    profile = await _make_profile(session, user=user, email="tokused@test.com")
    raw, rec = _make_deletion_token_row(profile)
    session.add(rec)
    await session.flush()
    token_id = rec.id

    storage = _mock_storage()
    await confirm_deletion(raw, session, storage=storage)

    token_row = await session.get(AccountDeletionToken, token_id)
    assert token_row is not None
    assert token_row.used is True


@pytest.mark.asyncio
async def test_confirm_deletion_writes_audit_event(session):
    user = await _make_user(session, email="auditdel@test.com")
    profile = await _make_profile(session, user=user, email="auditdel@test.com")
    raw, rec = _make_deletion_token_row(profile)
    session.add(rec)
    await session.flush()

    storage = _mock_storage()
    await confirm_deletion(raw, session, storage=storage)

    audit_rows = list(
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "account_deleted"  # type: ignore[arg-type]
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].target_type == "candidateprofile"


@pytest.mark.asyncio
async def test_confirm_deletion_invalid_token_raises(session):
    storage = _mock_storage()
    with pytest.raises(InvalidAccountDeletionTokenError):
        await confirm_deletion("bad-token", session, storage=storage)


@pytest.mark.asyncio
async def test_confirm_deletion_works_for_anonymous_profile(session):
    """Anonymous candidate (no User) can also be deleted."""
    profile = await _make_profile(session, email="anon@test.com")
    assert profile.user_id is None
    profile_id = profile.id
    raw, rec = _make_deletion_token_row(profile)
    session.add(rec)
    await session.flush()

    storage = _mock_storage()
    await confirm_deletion(raw, session, storage=storage)

    refreshed = await session.get(CandidateProfile, profile_id)
    assert refreshed is not None
    assert refreshed.deleted_at is not None


@pytest.mark.asyncio
async def test_confirm_deletion_token_reuse_raises(session_local_factory):
    """Consuming a token marks it used; replaying the same raw token must fail."""
    async with session_local_factory() as s1:
        user = await _make_user(s1, email="reuse@test.com")
        profile = await _make_profile(s1, user=user, email="reuse@test.com")
        raw, rec = _make_deletion_token_row(profile)
        s1.add(rec)
        await s1.commit()

    storage = _mock_storage()
    async with session_local_factory() as s2:
        await confirm_deletion(raw, s2, storage=storage)
        await s2.commit()

    async with session_local_factory() as s3:
        with pytest.raises(InvalidAccountDeletionTokenError):
            await confirm_deletion(raw, s3, storage=storage)
