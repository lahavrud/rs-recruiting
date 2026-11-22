"""Integration tests for the resume download endpoint."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from rs_shared.models import CandidateProfile, User
from tests.conftest import TestSessionLocal, audit_rows


@pytest.mark.asyncio
async def test_download_resume_requires_admin(public_client: AsyncClient):
    """Unauthenticated clients cannot download resumes."""
    response = await public_client.get("/api/resumes/test.pdf")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_download_resume_invalid_key(admin_client: AsyncClient):
    """Returns 400 for keys containing characters outside the safe set."""
    response = await admin_client.get("/api/resumes/invalid@key.pdf")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_download_resume_not_found(admin_client: AsyncClient, tmp_path: Path):
    """Returns 404 when the file does not exist in storage."""
    mock_settings = MagicMock()
    mock_settings.storage_provider = "local"
    mock_settings.local_storage_path = str(tmp_path)

    with patch("rs_api.api._resume_streaming.settings", mock_settings):
        response = await admin_client.get("/api/resumes/nonexistent.pdf")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_resume_success(admin_client: AsyncClient, tmp_path: Path):
    """Returns 200 and file content for a valid existing resume.

    Files live under `<storage>/resumes/<key>` (storage providers prepend
    the `resumes/` prefix on upload); the route re-adds that prefix before
    reading from disk.
    """
    fake_pdf = b"%PDF-1.4 fake content"
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "resume.pdf").write_bytes(fake_pdf)

    mock_settings = MagicMock()
    mock_settings.storage_provider = "local"
    mock_settings.local_storage_path = str(tmp_path)

    with patch("rs_api.api._resume_streaming.settings", mock_settings):
        response = await admin_client.get("/api/resumes/resume.pdf")

    assert response.status_code == 200
    assert response.content == fake_pdf


@pytest.mark.asyncio
async def test_download_resume_s3_proxies(admin_client: AsyncClient):
    """For S3 storage, streams the file bytes directly (no redirect).

    The key passed to the storage provider must include the `resumes/` prefix,
    since that's where files actually live under the bucket.
    """
    mock_settings = MagicMock()
    mock_settings.storage_provider = "s3"

    fake_pdf = b"%PDF-1.4 fake s3 content"
    received_keys: list[str] = []

    async def fake_download(key: str) -> bytes:
        received_keys.append(key)
        return fake_pdf

    mock_storage = MagicMock()
    mock_storage.download_file = fake_download

    with (
        patch("rs_api.api._resume_streaming.settings", mock_settings),
        patch(
            "rs_api.api._resume_streaming.get_storage_provider",
            return_value=mock_storage,
        ),
    ):
        response = await admin_client.get("/api/resumes/abc123.pdf")

    assert response.status_code == 200
    assert response.content == fake_pdf
    assert response.headers["content-type"] == "application/pdf"
    assert received_keys == ["resumes/abc123.pdf"]


@pytest.mark.asyncio
async def test_download_resume_audits_the_view(
    admin_client: AsyncClient,
    admin_user: User,
    candidate_profile: CandidateProfile,
    tmp_path: Path,
):
    """A served resume leaves a view row on its candidate."""
    async with TestSessionLocal() as s:
        profile = await s.get(CandidateProfile, candidate_profile.id)
        assert profile is not None
        profile.resume_path = "resumes/seen.pdf"
        await s.commit()
    (tmp_path / "resumes").mkdir()
    (tmp_path / "resumes" / "seen.pdf").write_bytes(b"%PDF-1.4 x")
    mock_settings = MagicMock()
    mock_settings.storage_provider = "local"
    mock_settings.local_storage_path = str(tmp_path)

    with patch("rs_api.api._resume_streaming.settings", mock_settings):
        response = await admin_client.get("/api/resumes/seen.pdf")

    assert response.status_code == 200
    [row] = await audit_rows("candidate.resume_view")
    assert (row.target_id, row.actor_user_id) == (candidate_profile.id, admin_user.id)


@pytest.mark.asyncio
async def test_download_resume_missing_file_is_not_audited(
    admin_client: AsyncClient, candidate_profile: CandidateProfile, tmp_path: Path
):
    """A 404 is not a view, even when a profile points at the key."""
    async with TestSessionLocal() as s:
        profile = await s.get(CandidateProfile, candidate_profile.id)
        assert profile is not None
        profile.resume_path = "resumes/gone.pdf"
        await s.commit()
    mock_settings = MagicMock()
    mock_settings.storage_provider = "local"
    mock_settings.local_storage_path = str(tmp_path)

    with patch("rs_api.api._resume_streaming.settings", mock_settings):
        response = await admin_client.get("/api/resumes/gone.pdf")

    assert response.status_code == 404
    assert await audit_rows("candidate.resume_view") == []
