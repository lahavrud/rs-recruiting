"""Tests for src/services/auth/session.py — token issuance, rotation, replay detection.

Login credential tests (authenticate_user) live in test_login.py.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import get_password_hash, hash_token
from src.enums import InviteTokenStatus, UserRole
from src.models import InviteToken, RefreshToken, UsedRefreshToken, User
from src.services.auth.session import (
    create_user_tokens,
    get_invite_by_hash,
    logout_user,
    refresh_user_tokens,
)
from src.services.exceptions import InvalidCredentialsError


def _active_user(email: str = "session-test@example.com") -> User:
    return User(
        email=email,
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
        is_active=True,
    )


# ── create_user_tokens ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_user_tokens_returns_token_pair(session: AsyncSession):
    """create_user_tokens returns non-empty access and refresh token strings."""
    user = _active_user()
    session.add(user)
    await session.commit()
    await session.refresh(user)

    access, refresh = await create_user_tokens(user, session)

    assert isinstance(access, str) and len(access) > 0
    assert isinstance(refresh, str) and len(refresh) > 0


@pytest.mark.asyncio
async def test_create_user_tokens_persists_refresh_row(session: AsyncSession):
    """create_user_tokens writes a RefreshToken row keyed by the returned raw token."""
    user = _active_user("persist@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, raw_refresh = await create_user_tokens(user, session)
    await session.commit()

    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(raw_refresh)  # pyright: ignore[reportArgumentType]
        )
    )
    db_token = result.scalar_one_or_none()
    assert db_token is not None
    assert db_token.user_id == user.id


@pytest.mark.asyncio
async def test_create_user_tokens_remember_me_stored(session: AsyncSession):
    """create_user_tokens stores the remember_me flag on the RefreshToken row."""
    user = _active_user("remember@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, raw_refresh = await create_user_tokens(user, session, remember_me=True)
    await session.commit()

    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(raw_refresh)  # pyright: ignore[reportArgumentType]
        )
    )
    assert result.scalar_one().remember_me is True


# ── refresh_user_tokens ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_user_tokens_rotates_token(session: AsyncSession):
    """refresh_user_tokens deletes the consumed row and issues a fresh pair."""
    user = _active_user("rotate@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, old_raw = await create_user_tokens(user, session)
    await session.commit()

    new_access, new_raw, _ = await refresh_user_tokens(old_raw, session)
    await session.commit()

    assert isinstance(new_access, str) and new_access
    assert isinstance(new_raw, str) and new_raw != old_raw

    old_result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(old_raw)  # pyright: ignore[reportArgumentType]
        )
    )
    assert old_result.scalar_one_or_none() is None


@pytest.mark.asyncio
@patch("src.services.auth.session._nuke_user_refresh_tokens", new_callable=AsyncMock)
async def test_refresh_user_tokens_single_use(
    _mock_nuke: AsyncMock,
    session: AsyncSession,
):
    """A consumed refresh token cannot be reused — second rotation raises
    InvalidCredentialsError."""
    user = _active_user("singleuse@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, old_raw = await create_user_tokens(user, session)
    await session.commit()

    await refresh_user_tokens(old_raw, session)
    await session.commit()

    with pytest.raises(InvalidCredentialsError):
        await refresh_user_tokens(old_raw, session)


@pytest.mark.asyncio
async def test_refresh_user_tokens_carries_remember_me(session: AsyncSession):
    """refresh_user_tokens propagates remember_me from the old token to the new one."""
    user = _active_user("rememberrotate@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, old_raw = await create_user_tokens(user, session, remember_me=True)
    await session.commit()

    _, new_raw, remember_me = await refresh_user_tokens(old_raw, session)
    await session.commit()

    assert remember_me is True
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(new_raw)  # pyright: ignore[reportArgumentType]
        )
    )
    assert result.scalar_one().remember_me is True


@pytest.mark.asyncio
async def test_refresh_user_tokens_invalid_token(session: AsyncSession):
    """refresh_user_tokens raises InvalidCredentialsError for an unknown token."""
    with pytest.raises(InvalidCredentialsError):
        await refresh_user_tokens("not-a-real-token", session)


@pytest.mark.asyncio
@patch("src.services.auth.session._delete_refresh_token", new_callable=AsyncMock)
async def test_refresh_user_tokens_expired_token(
    mock_delete: AsyncMock,
    session: AsyncSession,
):
    """refresh_user_tokens rejects an expired token and triggers its deletion.

    _delete_refresh_token is patched for the same reason as _mock_lockout_db_writes
    in conftest: it opens its own async_session which is bound to the base DATABASE_URL
    at import time, so in -n auto parallel runs it would write to the wrong worker DB.
    We verify the correct deletion call instead of querying the row absence.
    """
    user = _active_user("expired@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    raw_token = "test-expired-raw-token"
    db_token = RefreshToken(
        token_hash=hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        remember_me=False,
    )
    session.add(db_token)
    await session.commit()
    await session.refresh(db_token)

    with pytest.raises(InvalidCredentialsError):
        await refresh_user_tokens(raw_token, session)

    mock_delete.assert_awaited_once_with(db_token.id)


# ── logout_user ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logout_user_deletes_refresh_token(session: AsyncSession):
    """logout_user removes the refresh token row so the session cannot be reused."""
    user = _active_user("logout@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, raw = await create_user_tokens(user, session)
    await session.commit()

    await logout_user(raw, session)
    await session.commit()

    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(raw)  # pyright: ignore[reportArgumentType]
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_logout_user_noop_for_unknown_token(session: AsyncSession):
    """logout_user does not raise when the token is not in the database."""
    await logout_user("not-a-real-token", session)


@pytest.mark.asyncio
async def test_logout_user_noop_for_none(session: AsyncSession):
    """logout_user does not raise when passed None."""
    await logout_user(None, session)


# ── replay detection ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_records_used_hash(session: AsyncSession):
    """After rotation the consumed token hash is written to UsedRefreshToken."""
    user = _active_user("usedrecord@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, old_raw = await create_user_tokens(user, session)
    await session.commit()

    old_hash = hash_token(old_raw)
    await refresh_user_tokens(old_raw, session)
    await session.commit()

    result = await session.execute(
        select(UsedRefreshToken).where(
            UsedRefreshToken.token_hash == old_hash  # pyright: ignore[reportArgumentType]
        )
    )
    used = result.scalar_one_or_none()
    assert used is not None
    assert used.user_id == user.id


@pytest.mark.asyncio
@patch("src.services.auth.session._nuke_user_refresh_tokens", new_callable=AsyncMock)
async def test_refresh_replay_detected_nukes_sessions(
    mock_nuke: AsyncMock,
    session: AsyncSession,
):
    """Presenting a previously-consumed token triggers session nuke + 401.

    _nuke_user_refresh_tokens is patched for the same reason as _delete_refresh_token
    in the expired-token test: it opens its own async_session bound to the base
    DATABASE_URL, which is wrong in -n auto parallel runs.
    """
    user = _active_user("replay@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    raw_token = "replay-raw-token"
    used = UsedRefreshToken(
        token_hash=hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(used)
    await session.commit()

    with pytest.raises(InvalidCredentialsError):
        await refresh_user_tokens(raw_token, session)

    mock_nuke.assert_awaited_once_with(user.id)


@pytest.mark.asyncio
@patch("src.services.auth.session._nuke_user_refresh_tokens", new_callable=AsyncMock)
async def test_refresh_expired_used_hash_no_nuke(
    mock_nuke: AsyncMock,
    session: AsyncSession,
):
    """An expired UsedRefreshToken record does not trigger replay detection."""
    user = _active_user("expiredused@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    raw_token = "expired-used-raw-token"
    used = UsedRefreshToken(
        token_hash=hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    session.add(used)
    await session.commit()

    with pytest.raises(InvalidCredentialsError):
        await refresh_user_tokens(raw_token, session)

    mock_nuke.assert_not_called()


@pytest.mark.asyncio
async def test_logout_records_used_hash(session: AsyncSession):
    """logout_user writes the token hash to UsedRefreshToken."""
    user = _active_user("logoutused@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, raw = await create_user_tokens(user, session)
    await session.commit()

    token_hash = hash_token(raw)
    await logout_user(raw, session)
    await session.commit()

    result = await session.execute(
        select(UsedRefreshToken).where(
            UsedRefreshToken.token_hash == token_hash  # pyright: ignore[reportArgumentType]
        )
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
@patch("src.services.auth.session._nuke_user_refresh_tokens", new_callable=AsyncMock)
async def test_replay_after_logout_nukes_sessions(
    mock_nuke: AsyncMock,
    session: AsyncSession,
):
    """A token re-presented after logout is treated as a replay — nukes sessions."""
    user = _active_user("replaylogout@example.com")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    _, raw = await create_user_tokens(user, session)
    await session.commit()

    await logout_user(raw, session)
    await session.commit()

    with pytest.raises(InvalidCredentialsError):
        await refresh_user_tokens(raw, session)

    mock_nuke.assert_awaited_once_with(user.id)


# ── get_invite_by_hash ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_invite_by_hash_returns_matching_record(session: AsyncSession):
    """get_invite_by_hash finds the InviteToken row by its hashed token."""
    admin = User(
        email="invite-admin@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(admin)
    await session.commit()
    await session.refresh(admin)

    raw_token = "raw-invite-token"
    invite = InviteToken(
        token_hash=hash_token(raw_token),
        email="invitee@example.com",
        status=InviteTokenStatus.PENDING,
        created_by_admin_id=admin.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)

    record = await get_invite_by_hash(raw_token, session)

    assert record is not None
    assert record.id == invite.id
    assert record.email == "invitee@example.com"


@pytest.mark.asyncio
async def test_get_invite_by_hash_returns_none_for_unknown_token(
    session: AsyncSession,
):
    """get_invite_by_hash returns None when no record matches the hash."""
    record = await get_invite_by_hash("not-a-real-invite-token", session)

    assert record is None
