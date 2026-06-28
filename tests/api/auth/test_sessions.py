"""API tests for /api/auth/sessions endpoints (#645)."""

import itertools
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_user
from src.core.infrastructure.security import get_password_hash
from src.enums import UserRole
from src.main import app
from src.models import RefreshToken, UsedRefreshToken, User
from tests.conftest import TestSessionLocal


async def _override_session():
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def _install_session_override():
    app.dependency_overrides[get_session] = _override_session
    yield
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture(autouse=True)
def _clear_user_override():
    yield
    app.dependency_overrides.pop(get_current_user, None)


async def _seed_user(session: AsyncSession, email: str = "sess@test.com") -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash("Secret1!"),  # pragma: allowlist secret
        role=UserRole.CANDIDATE,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _override_user(user: User) -> None:
    async def _resolver() -> User:
        return user

    app.dependency_overrides[get_current_user] = _resolver


_counter = itertools.count()


async def _add_token(
    session: AsyncSession,
    user_id: int,
    *,
    expired: bool = False,
    user_agent: str | None = None,
) -> RefreshToken:
    delta = timedelta(days=-1) if expired else timedelta(days=7)
    token = RefreshToken(
        token_hash=f"hash-{user_id}-{next(_counter)}",
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + delta,
        user_agent=user_agent,
    )
    session.add(token)
    await session.commit()
    await session.refresh(token)
    return token


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_list_sessions_empty(test_db):
    async with TestSessionLocal() as session:
        user = await _seed_user(session)
        _override_user(user)

    async with await _client() as client:
        resp = await client.get("/api/auth/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_sessions_returns_active_tokens(test_db):
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120"
    async with TestSessionLocal() as session:
        user = await _seed_user(session, "list@test.com")
        token = await _add_token(session, user.id, user_agent=ua)  # type: ignore[arg-type]
        _override_user(user)

    async with await _client() as client:
        resp = await client.get("/api/auth/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == token.id
    assert body[0]["user_agent"] == ua


@pytest.mark.asyncio
async def test_list_sessions_user_agent_null(test_db):
    async with TestSessionLocal() as session:
        user = await _seed_user(session, "null-ua@test.com")
        await _add_token(session, user.id)  # type: ignore[arg-type]
        _override_user(user)

    async with await _client() as client:
        resp = await client.get("/api/auth/sessions")
    assert resp.status_code == 200
    assert resp.json()[0]["user_agent"] is None


@pytest.mark.asyncio
async def test_list_sessions_excludes_expired(test_db):
    async with TestSessionLocal() as session:
        user = await _seed_user(session, "expired@test.com")
        await _add_token(session, user.id, expired=True)  # type: ignore[arg-type]
        _override_user(user)

    async with await _client() as client:
        resp = await client.get("/api/auth/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_revoke_session_success(test_db):
    async with TestSessionLocal() as session:
        user = await _seed_user(session, "revoke@test.com")
        token = await _add_token(session, user.id)  # type: ignore[arg-type]
        token_id = token.id
        token_hash = token.token_hash
        _override_user(user)

    async with await _client() as client:
        resp = await client.delete(f"/api/auth/sessions/{token_id}")
    assert resp.status_code == 204

    async with TestSessionLocal() as session:
        remaining = await session.get(RefreshToken, token_id)
        assert remaining is None

        # Explicit revocation deletes the row directly without adding to
        # UsedRefreshToken — this avoids the replay-nuke path being triggered
        # if the revoked browser tries to refresh, which would log out other
        # sessions for the same user.
        used = (
            await session.execute(
                __import__("sqlalchemy")
                .select(UsedRefreshToken)
                .where(UsedRefreshToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        assert used is None


@pytest.mark.asyncio
async def test_revoke_session_not_found(test_db):
    async with TestSessionLocal() as session:
        user = await _seed_user(session, "notfound@test.com")
        _override_user(user)

    async with await _client() as client:
        resp = await client.delete("/api/auth/sessions/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revoke_session_wrong_user(test_db):
    """Trying to revoke another user's session returns 404 (not 403)."""
    async with TestSessionLocal() as session:
        owner = await _seed_user(session, "owner@test.com")
        attacker = await _seed_user(session, "attacker@test.com")
        token = await _add_token(session, owner.id)  # type: ignore[arg-type]
        _override_user(attacker)

    async with await _client() as client:
        resp = await client.delete(f"/api/auth/sessions/{token.id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revoke_all_sessions(test_db):
    async with TestSessionLocal() as session:
        user = await _seed_user(session, "revokeall@test.com")
        t1 = await _add_token(session, user.id)  # type: ignore[arg-type]
        t2 = await _add_token(session, user.id)  # type: ignore[arg-type]
        _override_user(user)

    async with await _client() as client:
        resp = await client.delete("/api/auth/sessions")
    assert resp.status_code == 204

    async with TestSessionLocal() as session:
        for tid in (t1.id, t2.id):
            assert await session.get(RefreshToken, tid) is None
