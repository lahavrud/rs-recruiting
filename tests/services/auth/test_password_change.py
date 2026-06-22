"""Service-level tests for the in-session password change (Sprint 11 / #608)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.infrastructure.security import (
    get_password_hash,
    hash_token,
    is_password_valid,
)
from src.enums import UserRole
from src.models import RefreshToken, User
from src.services.auth.password_change import change_user_password
from src.services.exceptions import InvalidCredentialsError


async def _make_user_with_tokens(
    session: AsyncSession,
    email: str = "pw@test.com",
) -> tuple[User, list[str]]:
    """Create a user + three valid refresh tokens. Returns (user, raw_tokens)."""
    user = User(
        email=email,
        hashed_password=get_password_hash("Original1!"),  # pragma: allowlist secret
        role=UserRole.CANDIDATE,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    raws = []
    for i in range(3):
        raw = f"refresh-token-{email}-{i}"
        session.add(
            RefreshToken(
                token_hash=hash_token(raw),
                user_id=user.id,
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
        )
        raws.append(raw)
    await session.flush()
    return user, raws


@pytest.mark.asyncio
async def test_change_password_with_correct_current_succeeds(session: AsyncSession):
    user, _ = await _make_user_with_tokens(session)
    await change_user_password(
        user,
        "Original1!",  # pragma: allowlist secret
        "FreshPass1!",  # pragma: allowlist secret
        current_refresh_token=None,
        session=session,
    )
    await session.commit()

    assert is_password_valid(
        "FreshPass1!",  # pragma: allowlist secret
        user.hashed_password,
    )


@pytest.mark.asyncio
async def test_change_password_with_wrong_current_raises(session: AsyncSession):
    user, _ = await _make_user_with_tokens(session, "wrong-current@test.com")
    with pytest.raises(InvalidCredentialsError):
        await change_user_password(
            user,
            "Wrong-Current1!",  # pragma: allowlist secret
            "Replacement1!",  # pragma: allowlist secret
            current_refresh_token=None,
            session=session,
        )


@pytest.mark.asyncio
async def test_change_password_revokes_only_other_refresh_tokens(
    session: AsyncSession,
):
    """The current session's refresh token survives; all others are deleted."""
    user, raws = await _make_user_with_tokens(session, "selective@test.com")
    current_raw = raws[1]  # arbitrary "current" session

    await change_user_password(
        user,
        "Original1!",  # pragma: allowlist secret
        "Rotated1!",  # pragma: allowlist secret
        current_refresh_token=current_raw,
        session=session,
    )
    await session.commit()

    remaining = (
        (
            await session.execute(
                select(RefreshToken).where(RefreshToken.user_id == user.id)  # type: ignore[arg-type]
            )
        )
        .scalars()
        .all()
    )
    # Only the current session's token row should remain.
    assert len(remaining) == 1
    assert remaining[0].token_hash == hash_token(current_raw)


@pytest.mark.asyncio
async def test_change_password_with_no_current_revokes_all(session: AsyncSession):
    """When no current token is supplied (e.g. mobile client), delete them all."""
    user, _ = await _make_user_with_tokens(session, "no-current@test.com")
    await change_user_password(
        user,
        "Original1!",  # pragma: allowlist secret
        "RotatedAll1!",  # pragma: allowlist secret
        current_refresh_token=None,
        session=session,
    )
    await session.commit()

    tokens = (
        (
            await session.execute(
                select(RefreshToken).where(RefreshToken.user_id == user.id)  # type: ignore[arg-type]
            )
        )
        .scalars()
        .all()
    )
    assert tokens == []
