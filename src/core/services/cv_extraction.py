"""CV text extraction + job text rendering for the resume-matching engine.

Pure functions over bytes/models — no storage or network access (the task
layer fetches resume bytes via the storage provider and passes them in here),
mirroring the bytes-in style of ``file_validation.py``.

Language note: extraction preserves text verbatim (Hebrew, English, or mixed)
and only normalizes whitespace. Do NOT add language-specific cleaning — the
embedding model is multilingual and matches across languages (see
``embeddings.py``).
"""

from __future__ import annotations

import io
import logging
import re
from typing import TYPE_CHECKING

from docx import Document
from pypdf import PdfReader

if TYPE_CHECKING:
    from src.models import Job

logger = logging.getLogger(__name__)

# Embedding APIs cap input length; resumes well under this are the norm. Cap
# defensively so a pathological file can't blow the request size.
_MAX_TEXT_CHARS = 50_000
_WHITESPACE_RE = re.compile(r"\s+")

# Extensions we can extract. Legacy binary ``.doc`` is intentionally excluded:
# python-docx reads only the OOXML ``.docx`` format. ``.doc`` uploads are
# allowed by the upload path but skipped here (logged, no crash).
_EXTRACTABLE = {"pdf", "docx"}


def _normalize(text: str) -> str:
    """Collapse runs of whitespace and cap length, preserving all scripts."""
    collapsed = _WHITESPACE_RE.sub(" ", text).strip()
    return collapsed[:_MAX_TEXT_CHARS]


def _extract_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    parts = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(parts)


def _extract_docx(content: bytes) -> str:
    document = Document(io.BytesIO(content))
    return "\n".join(p.text for p in document.paragraphs)


def extract_text(content: bytes, ext: str) -> str:
    """Extract plain text from a resume file's bytes.

    ``ext`` is the bare extension (no dot), case-insensitive. Returns ``""``
    for unsupported types (e.g. legacy ``.doc``) or when extraction yields
    nothing — callers treat empty text as "nothing to embed" and skip.
    """
    normalized_ext = ext.lower().lstrip(".")
    if normalized_ext not in _EXTRACTABLE:
        logger.info("cv_extract_unsupported_ext", extra={"ext": normalized_ext})
        return ""
    try:
        raw = (
            _extract_pdf(content) if normalized_ext == "pdf" else _extract_docx(content)
        )
    except Exception:
        # Corrupt/encrypted file — don't fail the whole match run.
        logger.warning(
            "cv_extract_failed", extra={"ext": normalized_ext}, exc_info=True
        )
        return ""
    return _normalize(raw)


def job_embedding_text(job: Job) -> str:
    """Render a Job into a single text blob for embedding.

    Concatenates every signal a match should consider: title, both
    descriptions, each requirement bullet, tags, and location.
    """
    parts: list[str] = [job.title, job.short_description, job.description]
    parts.extend(
        req["text"]
        for req in job.requirements
        if isinstance(req, dict) and req.get("text")
    )
    parts.extend(job.tags)
    if job.location:
        parts.append(job.location)
    return _normalize("\n".join(p for p in parts if p))
