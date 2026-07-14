"""Unit tests for services/utils/resume_upload.py — validate + upload a resume."""

import hashlib
from unittest.mock import AsyncMock

import pytest

from rs_shared.core.services.storage import StorageProvider
from rs_shared.services.utils.resume_upload import (
    _MAX_RESUME_BYTES,
    validate_and_upload_resume,
)

_PDF_BYTES = b"%PDF-1.4" + b"\x00" * 50


def _fake_storage(return_key: str = "resumes/resume.pdf") -> AsyncMock:
    storage = AsyncMock(spec=StorageProvider)
    storage.upload_file.return_value = return_key
    return storage


@pytest.mark.asyncio
async def test_valid_pdf_uploads_and_returns_key_and_hash():
    storage = _fake_storage()

    key, digest = await validate_and_upload_resume(_PDF_BYTES, "resume.pdf", storage)

    assert key == "resumes/resume.pdf"
    assert digest == hashlib.sha256(_PDF_BYTES).hexdigest()
    storage.upload_file.assert_awaited_once()
    assert storage.upload_file.await_args.kwargs["content_type"] == "application/pdf"


@pytest.mark.asyncio
async def test_disallowed_extension_rejected():
    with pytest.raises(ValueError, match="Invalid file type"):
        await validate_and_upload_resume(_PDF_BYTES, "resume.exe", _fake_storage())


@pytest.mark.asyncio
async def test_oversize_file_rejected():
    oversize = b"%PDF-1.4" + b"\x00" * (_MAX_RESUME_BYTES + 1)
    with pytest.raises(ValueError, match="exceeds maximum"):
        await validate_and_upload_resume(oversize, "resume.pdf", _fake_storage())


@pytest.mark.asyncio
async def test_forged_magic_bytes_rejected():
    """A .pdf whose bytes aren't actually a PDF is rejected before upload."""
    storage = _fake_storage()
    with pytest.raises(ValueError, match="does not match the declared file type"):
        await validate_and_upload_resume(b"not a real pdf", "resume.pdf", storage)
    storage.upload_file.assert_not_awaited()
