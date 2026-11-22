"""API tests for the candidate data-export endpoints (Sprint 11 / #608)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.infrastructure.dependencies import get_current_candidate
from rs_api.main import app
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.security import get_password_hash, hash_token
from rs_shared.enums import UserRole
from rs_shared.models import CandidateProfile, DataExportRequest, User
from tests.conftest import TestSessionLocal, audit_rows


async def _override_session():
    async with TestSessionLocal() as session:
        yield session


def _override_candidate(user: User, profile: CandidateProfile):
    async def _resolver() -> tuple[User, CandidateProfile]:
        return user, profile

    app.dependency_overrides[get_current_candidate] = _resolver


# Re-applied per-test because shared fixtures elsewhere in the suite call
# ``app.dependency_overrides.clear()`` on teardown, which would wipe a
# module-level assignment and route subsequent requests through the
# production engine.
@pytest.fixture(autouse=True)
def _isolate():
    app.dependency_overrides[get_session] = _override_session
    yield
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_candidate, None)


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_candidate(
    session: AsyncSession, email: str = "ex@test.com"
) -> tuple[User, CandidateProfile]:
    user = User(
        email=email,
        hashed_password=get_password_hash("Secret1!"),  # pragma: allowlist secret
        role=UserRole.CANDIDATE,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    profile = CandidateProfile(
        user_id=user.id,
        full_name="Export Test",
        email=email,
        phone="050-000-0001",
    )
    session.add(profile)
    await session.commit()
    await session.refresh(user)
    await session.refresh(profile)
    return user, profile


@pytest.mark.asyncio
async def test_post_export_enqueues_and_returns_202(test_db):
    async with TestSessionLocal() as session:
        user, profile = await _seed_candidate(session, "post-export@test.com")
    _override_candidate(user, profile)

    with patch(
        "rs_api.api.candidate.data_export.enqueue_data_export_task",
        new_callable=AsyncMock,
        return_value="inline",
    ) as mock_enqueue:
        async with await _client() as client:
            resp = await client.post("/api/candidate/me/export")
    assert resp.status_code == 202
    mock_enqueue.assert_awaited_once_with(user.id)


@pytest.mark.asyncio
async def test_post_export_blocks_when_pending_request_exists(test_db):
    async with TestSessionLocal() as session:
        user, profile = await _seed_candidate(session, "blocked@test.com")
        session.add(
            DataExportRequest(
                token_hash="pending-h",
                user_id=user.id,
                download_path="exports/p.zip",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
            )
        )
        await session.commit()
    _override_candidate(user, profile)

    async with await _client() as client:
        resp = await client.post("/api/candidate/me/export")
    assert resp.status_code == 429
    assert resp.json()["detail"] == "export_already_pending"


@pytest.mark.asyncio
async def test_get_export_streams_zip_and_marks_used(test_db):
    """Valid token → ZIP body returned and row.used flips to True."""
    raw_token = "valid-export-token"
    async with TestSessionLocal() as session:
        user, profile = await _seed_candidate(session, "stream@test.com")
        session.add(
            DataExportRequest(
                token_hash=hash_token(raw_token),
                user_id=user.id,
                download_path="exports/streamed.zip",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
            )
        )
        await session.commit()

    storage = AsyncMock()
    storage.download_file = AsyncMock(return_value=b"PK\x03\x04 fake zip body")

    with patch(
        "rs_api.api.candidate.data_export.get_storage_provider", return_value=storage
    ):
        async with await _client() as client:
            resp = await client.get(f"/api/candidate/me/export/{raw_token}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "attachment" in resp.headers["content-disposition"]
    storage.download_file.assert_awaited_once_with("exports/streamed.zip")

    async with TestSessionLocal() as session:
        from sqlmodel import select

        record = (
            await session.execute(
                select(DataExportRequest).where(
                    DataExportRequest.token_hash == hash_token(raw_token)  # type: ignore[arg-type]
                )
            )
        ).scalar_one()
        assert record.used is True

    # The candidate downloaded it, proven by the emailed token.
    [row] = await audit_rows("candidate.data_export_download")
    assert (row.target_type, row.target_id) == ("CandidateProfile", profile.id)
    assert row.actor_user_id == user.id


@pytest.mark.asyncio
async def test_get_export_used_token_returns_410(test_db):
    raw_token = "used-token"
    async with TestSessionLocal() as session:
        user, _ = await _seed_candidate(session, "used@test.com")
        session.add(
            DataExportRequest(
                token_hash=hash_token(raw_token),
                user_id=user.id,
                download_path="exports/x.zip",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
                used=True,
            )
        )
        await session.commit()

    async with await _client() as client:
        resp = await client.get(f"/api/candidate/me/export/{raw_token}")
    assert resp.status_code == 410
    assert resp.json()["detail"] == "export_already_used"


@pytest.mark.asyncio
async def test_get_export_expired_token_returns_410(test_db):
    raw_token = "expired-token"
    async with TestSessionLocal() as session:
        user, _ = await _seed_candidate(session, "expired@test.com")
        session.add(
            DataExportRequest(
                token_hash=hash_token(raw_token),
                user_id=user.id,
                download_path="exports/x.zip",
                expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
        await session.commit()

    async with await _client() as client:
        resp = await client.get(f"/api/candidate/me/export/{raw_token}")
    assert resp.status_code == 410
    assert resp.json()["detail"] == "export_expired"


@pytest.mark.asyncio
async def test_get_export_unknown_token_returns_404(test_db):
    async with await _client() as client:
        resp = await client.get("/api/candidate/me/export/does-not-exist-token")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "export_not_found"


@pytest.mark.asyncio
async def test_post_export_is_audited(test_db):
    """A GDPR export request starts a legal clock; it must leave a trace."""
    from sqlalchemy import select

    from rs_shared.models import AuditLog

    async with TestSessionLocal() as session:
        user, profile = await _seed_candidate(session, "audit-export@test.com")
    _override_candidate(user, profile)

    with patch(
        "rs_api.api.candidate.data_export.enqueue_data_export_task",
        new_callable=AsyncMock,
        return_value="inline",
    ):
        async with await _client() as client:
            resp = await client.post("/api/candidate/me/export")
    assert resp.status_code == 202

    async with TestSessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "candidate.data_export_request"  # pyright: ignore[reportArgumentType]
                    )
                )
            )
            .scalars()
            .all()
        )
    [row] = rows
    assert (row.target_type, row.target_id) == ("CandidateProfile", profile.id)
    assert row.actor_user_id == user.id
