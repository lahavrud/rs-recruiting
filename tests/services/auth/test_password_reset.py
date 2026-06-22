"""Service-level tests for the password-reset flow."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import (
    get_password_hash,
    hash_token,
    is_password_valid,
)
from src.core.infrastructure.transactions import transactional
from src.enums import UserRole
from src.models import PasswordResetToken, RefreshToken, User
from src.services.auth.password_reset import (
    _EMAIL_RATE_LIMIT_MAX,
    request_password_reset,
    reset_password,
    validate_password_reset_token,
)
from src.services.exceptions import InvalidPasswordResetTokenError


# Pull in the (no-longer-autouse) per-email rate-limit mock for every test in
# this file. Kept module-local so the global suite doesn't pay this setup.
@pytest.fixture(autouse=True)
def _bypass_password_reset_rate_limit(mock_password_reset_rate_limit):
    pass


async def _make_user(
    session: AsyncSession, email: str = "user@example.com", password: str = "OldPass1!"
) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_request_password_reset_mints_token_for_known_email(
    session: AsyncSession,
):
    user = await _make_user(session, email="real@example.com")

    async with transactional(session):
        await request_password_reset("real@example.com", session)

    result = await session.execute(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )
    tokens = result.scalars().all()
    assert len(tokens) == 1
    assert tokens[0].used is False


@pytest.mark.asyncio
async def test_request_password_reset_silent_for_unknown_email(session: AsyncSession):
    await _make_user(session, email="real@example.com")

    async with transactional(session):
        await request_password_reset("unknown@example.com", session)

    result = await session.execute(select(PasswordResetToken))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_request_password_reset_silent_on_empty_or_whitespace(
    session: AsyncSession,
):
    async with transactional(session):
        await request_password_reset("   ", session)
        await request_password_reset("", session)

    result = await session.execute(select(PasswordResetToken))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_per_email_rate_limit_skips_token_after_max_known_requests(
    session: AsyncSession,
):
    """4th request for the same known email must not mint a new token.

    The conftest-wide patch of _per_email_rate_limit_ok is bypassed here so
    we exercise the real limiter against an in-test fake.
    """
    user = await _make_user(session, email="victim@example.com")
    calls = {"n": 0}

    async def fake_limit(_user_id: int, _session: AsyncSession) -> bool:
        calls["n"] += 1
        return calls["n"] <= _EMAIL_RATE_LIMIT_MAX

    with patch(
        "src.services.auth.password_reset._per_email_rate_limit_ok",
        side_effect=fake_limit,
    ):
        for _ in range(_EMAIL_RATE_LIMIT_MAX + 1):
            async with transactional(session):
                await request_password_reset(user.email, session)

    result = await session.execute(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )
    assert len(result.scalars().all()) == _EMAIL_RATE_LIMIT_MAX


@pytest.mark.asyncio
async def test_reset_password_sets_new_hash_and_marks_token_used(
    session: AsyncSession,
):
    user = await _make_user(session, email="reset@example.com", password="OldPass1!")
    raw_token = "raw-token-success"
    record = PasswordResetToken(
        token_hash=hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        used=False,
    )
    session.add(record)
    await session.commit()

    async with transactional(session):
        await reset_password(raw_token, "BrandNewPass1!", session)

    await session.refresh(user)
    await session.refresh(record)
    assert record.used is True
    assert is_password_valid("BrandNewPass1!", user.hashed_password)
    assert not is_password_valid("OldPass1!", user.hashed_password)


@pytest.mark.asyncio
async def test_reset_password_revokes_all_refresh_tokens(session: AsyncSession):
    user = await _make_user(session, email="rotate@example.com")
    raw_token = "raw-token-rotate"
    session.add_all(
        [
            RefreshToken(
                token_hash="rt-a",
                user_id=user.id,
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            ),
            RefreshToken(
                token_hash="rt-b",
                user_id=user.id,
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            ),
            PasswordResetToken(
                token_hash=hash_token(raw_token),
                user_id=user.id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                used=False,
            ),
        ]
    )
    await session.commit()

    async with transactional(session):
        await reset_password(raw_token, "RotatedPass1!", session)

    result = await session.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )
    # Password reset deletes all refresh-token rows rather than marking them
    # revoked — rows deleted = no sessions survive.
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_reset_password_clears_lockout_state(session: AsyncSession):
    """Successful reset must defer a `_clear_failed_attempts` call after commit."""
    user = await _make_user(session, email="lock@example.com")
    raw_token = "raw-token-lockout"
    session.add(
        PasswordResetToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used=False,
        )
    )
    await session.commit()

    with patch(
        "src.services.auth.password_reset._clear_failed_attempts",
        new_callable=AsyncMock,
    ) as mock_clear:
        async with transactional(session):
            await reset_password(raw_token, "FreshPass1!", session)

    mock_clear.assert_called_once_with(user.id)


@pytest.mark.asyncio
async def test_reset_password_rejects_used_token(session: AsyncSession):
    user = await _make_user(session, email="used@example.com")
    raw_token = "raw-token-used"
    session.add(
        PasswordResetToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used=True,
        )
    )
    await session.commit()

    with pytest.raises(InvalidPasswordResetTokenError):
        async with transactional(session):
            await reset_password(raw_token, "WhateverPass1!", session)


@pytest.mark.asyncio
async def test_reset_password_rejects_expired_token(session: AsyncSession):
    user = await _make_user(session, email="exp@example.com")
    raw_token = "raw-token-expired"
    session.add(
        PasswordResetToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            used=False,
        )
    )
    await session.commit()

    with pytest.raises(InvalidPasswordResetTokenError):
        async with transactional(session):
            await reset_password(raw_token, "WhateverPass1!", session)


@pytest.mark.asyncio
async def test_reset_password_rejects_unknown_token(session: AsyncSession):
    with pytest.raises(InvalidPasswordResetTokenError):
        async with transactional(session):
            await reset_password("nonexistent-token", "WhateverPass1!", session)


@pytest.mark.asyncio
async def test_validate_token_returns_on_active(session: AsyncSession):
    user = await _make_user(session, email="ok@example.com")
    raw_token = "raw-validate-ok"
    session.add(
        PasswordResetToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used=False,
        )
    )
    await session.commit()

    await validate_password_reset_token(raw_token, session)  # must not raise


@pytest.mark.asyncio
async def test_validate_token_does_not_mark_used(session: AsyncSession):
    user = await _make_user(session, email="noconsume@example.com")
    raw_token = "raw-validate-noconsume"
    record = PasswordResetToken(
        token_hash=hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        used=False,
    )
    session.add(record)
    await session.commit()

    await validate_password_reset_token(raw_token, session)
    await session.refresh(record)
    assert record.used is False


@pytest.mark.asyncio
async def test_validate_token_rejects_used_expired_unknown(session: AsyncSession):
    user = await _make_user(session, email="rejects@example.com")
    raw_used = "raw-validate-used"
    raw_expired = "raw-validate-expired"
    session.add_all(
        [
            PasswordResetToken(
                token_hash=hash_token(raw_used),
                user_id=user.id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                used=True,
            ),
            PasswordResetToken(
                token_hash=hash_token(raw_expired),
                user_id=user.id,
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                used=False,
            ),
        ]
    )
    await session.commit()

    for bad in (raw_used, raw_expired, "totally-bogus"):
        with pytest.raises(InvalidPasswordResetTokenError):
            await validate_password_reset_token(bad, session)
