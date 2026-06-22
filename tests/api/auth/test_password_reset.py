"""Tests for password-reset endpoints (forgot-password + reset-password)."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.core.infrastructure.security import (
    get_password_hash,
    hash_token,
    is_password_valid,
)
from src.enums import UserRole
from src.models import PasswordResetToken, RefreshToken, User


# Pull in the (no-longer-autouse) per-email rate-limit mock for every test in
# this file. Kept module-local so the global suite doesn't pay this setup.
@pytest.fixture(autouse=True)
def _bypass_password_reset_rate_limit(mock_password_reset_rate_limit):
    pass


# `public_client` and `test_db` autouse fixtures come from tests/conftest.py.


async def _make_user(
    session, email: str = "user@example.com", password: str = "OldPass1!"
) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_forgot_password_response_identical_for_known_unknown_and_malformed(
    public_client: AsyncClient, session
):
    """Byte-identical response across known / unknown / malformed branches."""
    await _make_user(session, email="known@example.com")

    resp_known = await public_client.post(
        "/auth/forgot-password", json={"email": "known@example.com"}
    )
    resp_unknown = await public_client.post(
        "/auth/forgot-password", json={"email": "unknown@example.com"}
    )
    resp_malformed = await public_client.post(
        "/auth/forgot-password", json={"email": "not-an-email"}
    )

    assert resp_known.status_code == 200
    assert (
        resp_known.status_code == resp_unknown.status_code == resp_malformed.status_code
    )
    assert resp_known.content == resp_unknown.content == resp_malformed.content
    assert (
        resp_known.headers.get("content-type")
        == resp_unknown.headers.get("content-type")
        == resp_malformed.headers.get("content-type")
    )
    assert (
        resp_known.headers.get("content-length")
        == resp_unknown.headers.get("content-length")
        == resp_malformed.headers.get("content-length")
    )


@pytest.mark.asyncio
async def test_forgot_password_creates_token_only_for_known_email(
    public_client: AsyncClient, session
):
    """Known email mints a row in passwordresettoken; unknown does not."""
    from tests.conftest import TestSessionLocal

    await _make_user(session, email="real@example.com")

    await public_client.post(
        "/auth/forgot-password", json={"email": "real@example.com"}
    )
    await public_client.post(
        "/auth/forgot-password", json={"email": "fake@example.com"}
    )

    # API commits in its own session; open a fresh session to read.
    async with TestSessionLocal() as fresh:
        result = await fresh.execute(select(PasswordResetToken))
        tokens = result.scalars().all()
    assert len(tokens) == 1


@pytest.mark.asyncio
async def test_reset_password_success_changes_hash_and_marks_token_used(
    public_client: AsyncClient, session
):
    user = await _make_user(session, email="r1@example.com", password="OldPass1!")

    raw_token = "raw-reset-token-success"
    record = PasswordResetToken(
        token_hash=hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        used=False,
    )
    session.add(record)
    await session.commit()

    resp = await public_client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "BrandNewPass1!"},
    )
    assert resp.status_code == 200

    await session.refresh(user)
    await session.refresh(record)
    assert record.used is True
    assert is_password_valid("BrandNewPass1!", user.hashed_password)
    assert not is_password_valid("OldPass1!", user.hashed_password)


@pytest.mark.asyncio
async def test_reset_password_revokes_refresh_tokens(
    public_client: AsyncClient, session
):
    user = await _make_user(session, email="r2@example.com")

    rt_active = RefreshToken(
        token_hash="active-hash",
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        is_revoked=False,
    )
    rt_old = RefreshToken(
        token_hash="already-revoked-hash",
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        is_revoked=True,
    )
    session.add_all([rt_active, rt_old])
    raw_token = "raw-reset-revoke"
    session.add(
        PasswordResetToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used=False,
        )
    )
    await session.commit()

    resp = await public_client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "RotatedPass1!"},
    )
    assert resp.status_code == 200

    # The endpoint commits in its own session; open a fresh one to re-read state.
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as fresh:
        result = await fresh.execute(
            select(RefreshToken).where(RefreshToken.user_id == user.id)
        )
        tokens = result.scalars().all()
    assert all(t.is_revoked for t in tokens)


@pytest.mark.asyncio
async def test_reset_password_rejects_used_token(public_client: AsyncClient, session):
    user = await _make_user(session, email="r3@example.com")
    raw_token = "raw-reset-used"
    session.add(
        PasswordResetToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used=True,
        )
    )
    await session.commit()

    resp = await public_client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "WhateverPass1!"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_rejects_expired_token(
    public_client: AsyncClient, session
):
    user = await _make_user(session, email="r4@example.com")
    raw_token = "raw-reset-expired"
    session.add(
        PasswordResetToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            used=False,
        )
    )
    await session.commit()

    resp = await public_client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "WhateverPass1!"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_validate_reset_token_returns_200_for_active_token(
    public_client: AsyncClient, session
):
    user = await _make_user(session, email="v1@example.com")
    raw_token = "raw-validate-active"
    session.add(
        PasswordResetToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used=False,
        )
    )
    await session.commit()

    resp = await public_client.get(
        "/auth/reset-password/validate", params={"token": raw_token}
    )
    assert resp.status_code == 200
    assert resp.json() == {"valid": True}


@pytest.mark.asyncio
async def test_validate_reset_token_does_not_consume_token(
    public_client: AsyncClient, session
):
    """Validation must leave the token usable — otherwise the form submit dies."""
    user = await _make_user(session, email="v2@example.com")
    raw_token = "raw-validate-nonconsume"
    session.add(
        PasswordResetToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used=False,
        )
    )
    await session.commit()

    await public_client.get(
        "/auth/reset-password/validate", params={"token": raw_token}
    )
    resp = await public_client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "FreshPass1!"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_validate_reset_token_rejects_used(public_client: AsyncClient, session):
    user = await _make_user(session, email="v3@example.com")
    raw_token = "raw-validate-used"
    session.add(
        PasswordResetToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used=True,
        )
    )
    await session.commit()

    resp = await public_client.get(
        "/auth/reset-password/validate", params={"token": raw_token}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_validate_reset_token_rejects_expired(
    public_client: AsyncClient, session
):
    user = await _make_user(session, email="v4@example.com")
    raw_token = "raw-validate-expired"
    session.add(
        PasswordResetToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            used=False,
        )
    )
    await session.commit()

    resp = await public_client.get(
        "/auth/reset-password/validate", params={"token": raw_token}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_validate_reset_token_rejects_unknown(public_client: AsyncClient):
    resp = await public_client.get(
        "/auth/reset-password/validate", params={"token": "totally-bogus"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_rejects_unknown_token(public_client: AsyncClient):
    resp = await public_client.post(
        "/auth/reset-password",
        json={"token": "totally-bogus", "new_password": "WhateverPass1!"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_rejects_weak_password(
    public_client: AsyncClient, session
):
    user = await _make_user(session, email="r5@example.com")
    raw_token = "raw-reset-weak"
    session.add(
        PasswordResetToken(
            token_hash=hash_token(raw_token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used=False,
        )
    )
    await session.commit()

    resp = await public_client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "weak"},
    )
    assert resp.status_code == 422
