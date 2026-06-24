"""Tests for CV text extraction + job text rendering."""

import io
from unittest.mock import MagicMock, patch

from docx import Document

from src.core.services.cv_extraction import extract_text, job_embedding_text


def _make_docx(text: str) -> bytes:
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# extract_text
# ---------------------------------------------------------------------------


def test_extract_text_docx_real_roundtrip():
    content = _make_docx("Python developer\nשלום עולם")
    out = extract_text(content, "docx")
    assert "Python developer" in out
    assert "שלום עולם" in out  # Hebrew preserved verbatim


def test_extract_text_ext_is_case_insensitive_and_dot_tolerant():
    content = _make_docx("hello world")
    assert extract_text(content, "DOCX") == "hello world"
    assert extract_text(content, ".docx") == "hello world"


def test_extract_text_collapses_whitespace():
    page = MagicMock()
    page.extract_text.return_value = "Resume   text\n\n  here"
    reader = MagicMock()
    reader.pages = [page]
    with patch("src.core.services.cv_extraction.PdfReader", return_value=reader):
        assert extract_text(b"%PDF-fake", "pdf") == "Resume text here"


def test_extract_text_legacy_doc_is_skipped():
    # Legacy binary .doc is unsupported — return "" rather than crashing.
    assert extract_text(b"\xd0\xcf\x11\xe0 legacy doc", "doc") == ""


def test_extract_text_unknown_extension_returns_empty():
    assert extract_text(b"whatever", "txt") == ""


def test_extract_text_corrupt_docx_returns_empty():
    # Not a real zip/docx — extraction raises and is swallowed.
    assert extract_text(b"not a real docx", "docx") == ""


# ---------------------------------------------------------------------------
# job_embedding_text
# ---------------------------------------------------------------------------


def test_job_embedding_text_includes_all_signals():
    job = MagicMock()
    job.title = "Senior Engineer"
    job.short_description = "Great role"
    job.description = "Build things"
    job.requirements = [{"text": "Python"}, {"text": "SQL"}, {"missing": "x"}]
    job.tags = ["backend", "remote"]
    job.location = "Tel Aviv"

    out = job_embedding_text(job)

    for term in [
        "Senior Engineer",
        "Great role",
        "Build things",
        "Python",
        "SQL",
        "backend",
        "remote",
        "Tel Aviv",
    ]:
        assert term in out


def test_job_embedding_text_tolerates_malformed_requirements():
    job = MagicMock()
    job.title = "Role"
    job.short_description = "Short"
    job.description = "Desc"
    job.requirements = ["not a dict", {"text": ""}, {"text": "Kept"}]
    job.tags = []
    job.location = ""

    out = job_embedding_text(job)
    assert "Kept" in out
    assert "Role" in out
