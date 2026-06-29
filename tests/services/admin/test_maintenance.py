"""Tests for nightly data-hygiene helpers (services/admin/maintenance.py)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import hash_token
from rs_shared.enums import UserRole
from rs_shared.models import (
    AccountDeletionToken,
    ActivationToken,
    CandidateProfile,
    DataExportRequest,
    User,
)
from rs_shared.services.admin.maintenance import (
    purge_expired_account_deletion_tokens,
    purge_expired_activation_tokens,
    purge_expired_data_export_zips,
    purge_unactivated_candidate_users,
)
from tests.conftest import TestSessionLocal

_NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_candidate_user(
    session: AsyncSession,
    *,
    email: str = "test@example.com",
    is_active: bool = False,
    created_at: datetime | None = None,
    role: UserRole = UserRole.CANDIDATE,
) -> User:
    user = User(
        email=email,
        hashed_password="hashed",
        role=role,
        is_active=is_active,
        created_at=created_at or _NOW,
    )
    session.add(user)
    await session.flush()
    return user


async def _make_activation_token(
    session: AsyncSession,
    user: User,
    *,
    used: bool = False,
    expires_at: datetime | None = None,
) -> ActivationToken:
    token = ActivationToken(
        token_hash=hash_token(secrets.token_urlsafe(32)),
        user_id=user.id,
        expires_at=expires_at or (_NOW + timedelta(hours=48)),
        used=used,
    )
    session.add(token)
    await session.flush()
    return token


async def _make_profile(
    session: AsyncSession,
    *,
    email: str = "cand@example.com",
    user: User | None = None,
) -> CandidateProfile:
    profile = CandidateProfile(
        full_name="Test Candidate",
        email=email,
        user_id=user.id if user else None,
    )
    session.add(profile)
    await session.flush()
    return profile


async def _make_data_export(
    session: AsyncSession,
    *,
    user_id: int,
    used: bool = False,
    expires_at: datetime | None = None,
    created_at: datetime | None = None,
) -> DataExportRequest:
    row = DataExportRequest(
        token_hash=hash_token(secrets.token_urlsafe(32)),
        user_id=user_id,
        download_path="exports/1/test.zip",
        expires_at=expires_at or (_NOW + timedelta(hours=24)),
        used=used,
        created_at=created_at or _NOW,
    )
    session.add(row)
    await session.flush()
    return row


async def _make_deletion_token(
    session: AsyncSession,
    *,
    profile: CandidateProfile,
    used: bool = False,
    expires_at: datetime | None = None,
) -> AccountDeletionToken:
    token = AccountDeletionToken(
        token_hash=hash_token(secrets.token_urlsafe(32)),
        candidate_profile_id=profile.id,
        expires_at=expires_at or (_NOW + timedelta(hours=24)),
        used=used,
    )
    session.add(token)
    await session.flush()
    return token


# ---------------------------------------------------------------------------
# purge_unactivated_candidate_users
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_purge_unactivated_deletes_old_inactive_candidate(session):
    user = await _make_candidate_user(
        session,
        email="old@test.com",
        is_active=False,
        created_at=_NOW - timedelta(days=8),
    )
    user_id = user.id

    count = await purge_unactivated_candidate_users(session)

    assert count == 1
    assert await session.get(User, user_id) is None


@pytest.mark.asyncio
async def test_purge_unactivated_preserves_recent_inactive_candidate(session):
    user = await _make_candidate_user(
        session,
        email="recent@test.com",
        is_active=False,
        created_at=_NOW - timedelta(days=6),
    )
    count = await purge_unactivated_candidate_users(session)

    assert count == 0
    assert await session.get(User, user.id) is not None


@pytest.mark.asyncio
async def test_purge_unactivated_preserves_user_with_valid_pending_token(session):
    user = await _make_candidate_user(
        session,
        email="has_token@test.com",
        is_active=False,
        created_at=_NOW - timedelta(days=10),
    )
    await _make_activation_token(
        session,
        user,
        used=False,
        expires_at=_NOW + timedelta(hours=24),
    )

    count = await purge_unactivated_candidate_users(session)

    assert count == 0
    assert await session.get(User, user.id) is not None


@pytest.mark.asyncio
async def test_purge_unactivated_deletes_user_with_only_used_or_expired_token(session):
    user = await _make_candidate_user(
        session,
        email="stale_token@test.com",
        is_active=False,
        created_at=_NOW - timedelta(days=10),
    )
    # used token
    await _make_activation_token(
        session,
        user,
        used=True,
        expires_at=_NOW - timedelta(hours=1),
    )
    user_id = user.id

    count = await purge_unactivated_candidate_users(session)

    assert count == 1
    assert await session.get(User, user_id) is None


@pytest.mark.asyncio
async def test_purge_unactivated_preserves_active_candidate(session):
    user = await _make_candidate_user(
        session,
        email="active@test.com",
        is_active=True,
        created_at=_NOW - timedelta(days=10),
    )
    count = await purge_unactivated_candidate_users(session)

    assert count == 0
    assert await session.get(User, user.id) is not None


@pytest.mark.asyncio
async def test_purge_unactivated_preserves_non_candidate_role(session):
    user = await _make_candidate_user(
        session,
        email="admin@test.com",
        is_active=False,
        created_at=_NOW - timedelta(days=10),
        role=UserRole.ADMIN,
    )
    count = await purge_unactivated_candidate_users(session)

    assert count == 0
    assert await session.get(User, user.id) is not None


@pytest.mark.asyncio
async def test_purge_unactivated_sets_profile_user_id_to_null(session):
    """Deleting a pending User leaves its CandidateProfile as an anonymous lead."""
    user = await _make_candidate_user(
        session,
        email="linked@test.com",
        is_active=False,
        created_at=_NOW - timedelta(days=10),
    )
    profile = await _make_profile(session, email="linked_p@test.com", user=user)
    profile_id = profile.id

    await purge_unactivated_candidate_users(session)
    await session.flush()

    # Profile survives; user_id is NULLed by the FK SET NULL cascade.
    refreshed = await session.get(CandidateProfile, profile_id)
    assert refreshed is not None
    assert refreshed.user_id is None


# ---------------------------------------------------------------------------
# purge_expired_data_export_zips
# ---------------------------------------------------------------------------


def _mock_storage(fail: bool = False):
    storage = MagicMock()
    if fail:
        storage.delete_file = AsyncMock(side_effect=Exception("S3 error"))
    else:
        storage.delete_file = AsyncMock(return_value=True)
    return storage


@pytest.mark.asyncio
async def test_purge_export_zips_deletes_expired_row(session):
    async with TestSessionLocal() as s2:
        user = await _make_candidate_user(s2, email="exp@test.com", is_active=True)
        row = await _make_data_export(
            s2, user_id=user.id, expires_at=_NOW - timedelta(hours=1)
        )
        row_id = row.id
        await s2.commit()

    mock_storage = _mock_storage()
    with patch(
        "rs_shared.services.admin.maintenance.get_storage_provider",
        return_value=mock_storage,
    ):
        async with TestSessionLocal() as s3:
            count = await purge_expired_data_export_zips(s3)
            await s3.commit()

    assert count == 1
    async with TestSessionLocal() as s4:
        assert await s4.get(DataExportRequest, row_id) is None
    mock_storage.delete_file.assert_awaited_once_with("exports/1/test.zip")


@pytest.mark.asyncio
async def test_purge_export_zips_deletes_used_old_row(session):
    cutoff = _NOW - timedelta(hours=25)
    async with TestSessionLocal() as s2:
        user = await _make_candidate_user(s2, email="used@test.com", is_active=True)
        row = await _make_data_export(
            s2,
            user_id=user.id,
            used=True,
            created_at=cutoff,
            expires_at=cutoff + timedelta(hours=24),
        )
        row_id = row.id
        await s2.commit()

    mock_storage = _mock_storage()
    with patch(
        "rs_shared.services.admin.maintenance.get_storage_provider",
        return_value=mock_storage,
    ):
        async with TestSessionLocal() as s3:
            count = await purge_expired_data_export_zips(s3)
            await s3.commit()

    assert count == 1
    async with TestSessionLocal() as s4:
        assert await s4.get(DataExportRequest, row_id) is None


@pytest.mark.asyncio
async def test_purge_export_zips_preserves_active_row(session):
    async with TestSessionLocal() as s2:
        user = await _make_candidate_user(
            s2, email="active_exp@test.com", is_active=True
        )
        row = await _make_data_export(
            s2, user_id=user.id, used=False, expires_at=_NOW + timedelta(hours=20)
        )
        row_id = row.id
        await s2.commit()

    mock_storage = _mock_storage()
    with patch(
        "rs_shared.services.admin.maintenance.get_storage_provider",
        return_value=mock_storage,
    ):
        async with TestSessionLocal() as s3:
            count = await purge_expired_data_export_zips(s3)
            await s3.commit()

    assert count == 0
    async with TestSessionLocal() as s4:
        assert await s4.get(DataExportRequest, row_id) is not None


@pytest.mark.asyncio
async def test_purge_export_zips_preserves_row_on_storage_failure(session):
    """Storage failure is best-effort: row is preserved rather than orphaned."""
    async with TestSessionLocal() as s2:
        user = await _make_candidate_user(s2, email="fail@test.com", is_active=True)
        row = await _make_data_export(
            s2, user_id=user.id, expires_at=_NOW - timedelta(hours=1)
        )
        row_id = row.id
        await s2.commit()

    mock_storage = _mock_storage(fail=True)
    with patch(
        "rs_shared.services.admin.maintenance.get_storage_provider",
        return_value=mock_storage,
    ):
        async with TestSessionLocal() as s3:
            count = await purge_expired_data_export_zips(s3)
            await s3.commit()

    assert count == 0
    async with TestSessionLocal() as s4:
        assert await s4.get(DataExportRequest, row_id) is not None


# ---------------------------------------------------------------------------
# purge_expired_account_deletion_tokens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_purge_deletion_tokens_deletes_expired(session):
    profile = await _make_profile(session, email="del_exp@test.com")
    token = await _make_deletion_token(
        session, profile=profile, expires_at=_NOW - timedelta(hours=1)
    )
    token_id = token.id

    count = await purge_expired_account_deletion_tokens(session)

    assert count == 1
    assert await session.get(AccountDeletionToken, token_id) is None


@pytest.mark.asyncio
async def test_purge_deletion_tokens_deletes_used(session):
    profile = await _make_profile(session, email="del_used@test.com")
    token = await _make_deletion_token(
        session,
        profile=profile,
        used=True,
        expires_at=_NOW + timedelta(hours=20),
    )
    token_id = token.id

    count = await purge_expired_account_deletion_tokens(session)

    assert count == 1
    assert await session.get(AccountDeletionToken, token_id) is None


@pytest.mark.asyncio
async def test_purge_deletion_tokens_preserves_active(session):
    profile = await _make_profile(session, email="del_active@test.com")
    token = await _make_deletion_token(
        session,
        profile=profile,
        used=False,
        expires_at=_NOW + timedelta(hours=20),
    )
    token_id = token.id

    count = await purge_expired_account_deletion_tokens(session)

    assert count == 0
    assert await session.get(AccountDeletionToken, token_id) is not None


# ---------------------------------------------------------------------------
# purge_expired_activation_tokens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_purge_activation_tokens_deletes_old_expired(session):
    user = await _make_candidate_user(session, email="old_act@test.com", is_active=True)
    token = await _make_activation_token(
        session,
        user,
        used=False,
        expires_at=_NOW - timedelta(days=31),
    )
    token_id = token.id

    count = await purge_expired_activation_tokens(session)

    assert count == 1
    assert await session.get(ActivationToken, token_id) is None


@pytest.mark.asyncio
async def test_purge_activation_tokens_preserves_recently_expired(session):
    """Tokens expired within the 30-day grace window are retained."""
    user = await _make_candidate_user(
        session, email="recent_exp@test.com", is_active=True
    )
    token = await _make_activation_token(
        session,
        user,
        used=False,
        expires_at=_NOW - timedelta(days=15),
    )
    token_id = token.id

    count = await purge_expired_activation_tokens(session)

    assert count == 0
    assert await session.get(ActivationToken, token_id) is not None


@pytest.mark.asyncio
async def test_purge_activation_tokens_deletes_old_used(session):
    user = await _make_candidate_user(
        session, email="old_used@test.com", is_active=True
    )
    token = await _make_activation_token(
        session,
        user,
        used=True,
        expires_at=_NOW - timedelta(days=31),
    )
    token_id = token.id

    count = await purge_expired_activation_tokens(session)

    assert count == 1
    assert await session.get(ActivationToken, token_id) is None
