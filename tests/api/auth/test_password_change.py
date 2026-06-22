"""API tests for /auth/me/password (Sprint 11 / #608)."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_user
from src.core.infrastructure.security import (
    get_password_hash,
    hash_token,
    is_password_valid,
)
from src.enums import UserRole
from src.main import app
from src.models import RefreshToken, User
from tests.conftest import TestSessionLocal


async def _override_session():
    async with TestSessionLocal() as session:
        yield session


def _override_user(user: User):
    async def _resolver() -> User:
        return user

    app.dependency_overrides[get_current_user] = _resolver


# Re-applied per-test because shared fixtures elsewhere in the suite call
# ``app.dependency_overrides.clear()`` on teardown, which would wipe a
# module-level assignment and route subsequent requests through the
# production engine.
@pytest.fixture(autouse=True)
def _isolate():
    app.dependency_overrides[get_session] = _override_session
    yield
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _make_user(
    session: AsyncSession,
    email: str,
    role: UserRole = UserRole.CANDIDATE,
) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash("Original1!"),  # pragma: allowlist secret
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_change_password_success_for_candidate(test_db):
    async with TestSessionLocal() as session:
        user = await _make_user(session, "ok-cand@test.com")
    _override_user(user)

    async with await _client() as client:
        resp = await client.post(
            "/auth/me/password",
            json={
                "current_password": "Original1!",  # pragma: allowlist secret
                "new_password": "RotatedAA1!",  # pragma: allowlist secret
            },
        )
    assert resp.status_code == 204

    async with TestSessionLocal() as session:
        from sqlmodel import select

        refreshed = (
            await session.execute(
                select(User).where(User.email == "ok-cand@test.com")  # type: ignore[arg-type]
            )
        ).scalar_one()
        assert is_password_valid(
            "RotatedAA1!",  # pragma: allowlist secret
            refreshed.hashed_password,
        )


@pytest.mark.asyncio
async def test_change_password_rejects_wrong_current_with_401(test_db):
    async with TestSessionLocal() as session:
        user = await _make_user(session, "wrong-cur@test.com")
    _override_user(user)

    async with await _client() as client:
        resp = await client.post(
            "/auth/me/password",
            json={
                "current_password": "WrongCurrent1!",  # pragma: allowlist secret
                "new_password": "ReplaceAA1!",  # pragma: allowlist secret
            },
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "current_password_incorrect"


@pytest.mark.asyncio
async def test_change_password_rejects_weak_new_with_422(test_db):
    async with TestSessionLocal() as session:
        user = await _make_user(session, "weak@test.com")
    _override_user(user)

    async with await _client() as client:
        resp = await client.post(
            "/auth/me/password",
            json={
                "current_password": "Original1!",  # pragma: allowlist secret
                "new_password": "short",  # pragma: allowlist secret
            },
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_change_password_revokes_other_sessions(test_db):
    """Sending the current session's refresh cookie keeps that row;
    all other refresh-token rows are deleted (#641)."""
    async with TestSessionLocal() as session:
        user = await _make_user(session, "rotate@test.com")
        raw_keep = "refresh-keep-this-one"
        raw_revoke = "refresh-revoke-this-one"
        session.add_all(
            [
                RefreshToken(
                    token_hash=hash_token(raw_keep),
                    user_id=user.id,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                ),
                RefreshToken(
                    token_hash=hash_token(raw_revoke),
                    user_id=user.id,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                ),
            ]
        )
        await session.commit()

    _override_user(user)

    async with await _client() as client:
        client.cookies.set("refresh_token", raw_keep)
        resp = await client.post(
            "/auth/me/password",
            json={
                "current_password": "Original1!",  # pragma: allowlist secret
                "new_password": "Rotated1!",  # pragma: allowlist secret
            },
        )
    assert resp.status_code == 204

    async with TestSessionLocal() as session:
        from sqlmodel import select

        tokens = (
            (
                await session.execute(
                    select(RefreshToken).where(RefreshToken.user_id == user.id)  # type: ignore[arg-type]
                )
            )
            .scalars()
            .all()
        )
        # Only the current session's row must survive; the other is deleted.
        assert len(tokens) == 1
        assert tokens[0].token_hash == hash_token(raw_keep)


@pytest.mark.asyncio
async def test_change_password_works_for_admin(test_db):
    """Role-agnostic endpoint — admin sessions can change their own password."""
    async with TestSessionLocal() as session:
        admin = await _make_user(session, "admin@test.com", role=UserRole.ADMIN)
    _override_user(admin)

    async with await _client() as client:
        resp = await client.post(
            "/auth/me/password",
            json={
                "current_password": "Original1!",  # pragma: allowlist secret
                "new_password": "AdminPass1!",  # pragma: allowlist secret
            },
        )
    assert resp.status_code == 204
