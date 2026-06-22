"""Tests for magic byte file validation."""

from src.core.services.file_validation import (
    is_valid_document_magic_bytes,
    is_valid_image_magic_bytes,
)

# ── Real magic byte headers ───────────────────────────────────────────────────

_JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 100
_PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
_GIF87_HEADER = b"GIF87a" + b"\x00" * 100
_GIF89_HEADER = b"GIF89a" + b"\x00" * 100
_WEBP_HEADER = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
_PDF_HEADER = b"%PDF-1.4" + b"\x00" * 100
_DOC_HEADER = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100
_DOCX_HEADER = b"PK\x03\x04" + b"\x00" * 100

_EXE_HEADER = b"MZ" + b"\x00" * 100  # Windows PE


# ── Image validation ──────────────────────────────────────────────────────────


def test_jpeg_valid():
    assert is_valid_image_magic_bytes(_JPEG_HEADER, "image/jpeg") is True


def test_png_valid():
    assert is_valid_image_magic_bytes(_PNG_HEADER, "image/png") is True


def test_gif87_valid():
    assert is_valid_image_magic_bytes(_GIF87_HEADER, "image/gif") is True


def test_gif89_valid():
    assert is_valid_image_magic_bytes(_GIF89_HEADER, "image/gif") is True


def test_webp_valid():
    assert is_valid_image_magic_bytes(_WEBP_HEADER, "image/webp") is True


def test_exe_disguised_as_jpeg():
    assert is_valid_image_magic_bytes(_EXE_HEADER, "image/jpeg") is False


def test_exe_disguised_as_png():
    assert is_valid_image_magic_bytes(_EXE_HEADER, "image/png") is False


def test_jpeg_declared_as_png():
    assert is_valid_image_magic_bytes(_JPEG_HEADER, "image/png") is False


def test_png_declared_as_jpeg():
    assert is_valid_image_magic_bytes(_PNG_HEADER, "image/jpeg") is False


def test_pdf_declared_as_image():
    assert is_valid_image_magic_bytes(_PDF_HEADER, "image/jpeg") is False


def test_empty_data_image():
    assert is_valid_image_magic_bytes(b"", "image/jpeg") is False


def test_unknown_mime_type():
    assert is_valid_image_magic_bytes(_JPEG_HEADER, "image/tiff") is False


# ── Document validation ───────────────────────────────────────────────────────


def test_pdf_valid():
    assert is_valid_document_magic_bytes(_PDF_HEADER, "pdf") is True


def test_doc_valid():
    assert is_valid_document_magic_bytes(_DOC_HEADER, "doc") is True


def test_docx_valid():
    assert is_valid_document_magic_bytes(_DOCX_HEADER, "docx") is True


def test_exe_disguised_as_pdf():
    assert is_valid_document_magic_bytes(_EXE_HEADER, "pdf") is False


def test_exe_disguised_as_doc():
    assert is_valid_document_magic_bytes(_EXE_HEADER, "doc") is False


def test_exe_disguised_as_docx():
    assert is_valid_document_magic_bytes(_EXE_HEADER, "docx") is False


def test_pdf_declared_as_doc():
    assert is_valid_document_magic_bytes(_PDF_HEADER, "doc") is False


def test_docx_declared_as_pdf():
    assert is_valid_document_magic_bytes(_DOCX_HEADER, "pdf") is False


def test_empty_data_document():
    assert is_valid_document_magic_bytes(b"", "pdf") is False


def test_unknown_extension():
    assert is_valid_document_magic_bytes(_PDF_HEADER, "txt") is False


# ── WebP edge cases ───────────────────────────────────────────────────────────


def test_webp_wrong_riff():
    bad = b"XXXX\x00\x00\x00\x00WEBP" + b"\x00" * 100
    assert is_valid_image_magic_bytes(bad, "image/webp") is False


def test_webp_wrong_type():
    bad = b"RIFF\x00\x00\x00\x00JPEG" + b"\x00" * 100
    assert is_valid_image_magic_bytes(bad, "image/webp") is False


def test_webp_too_short():
    assert is_valid_image_magic_bytes(b"RIFF", "image/webp") is False
