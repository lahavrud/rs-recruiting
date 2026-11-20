"""Tests for the resume-matching tasks and scoring helpers (core/matching.py)."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from docx import Document

from rs_shared.core.matching import (
    _extension_of,
    cosine_similarity_score,
    embed_job_task,
    match_candidate_task,
)
from rs_shared.enums import JobStatus
from rs_shared.models import (
    CandidateProfile,
    Job,
)
from tests.conftest import TestSessionLocal

# ---------------------------------------------------------------------------
# Resume-matching tasks — embed_job_task / match_candidate_task
# ---------------------------------------------------------------------------


def _make_resume_docx(text: str) -> bytes:
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


async def _make_published_job(company_id: int, **overrides) -> int:
    defaults = dict(
        company_id=company_id,
        title="Senior Python Developer",
        short_description="Backend python role on a small team.",
        description="We need python fastapi postgresql backend experience.",
        requirements=[
            {"text": "Python"},
            {"text": "FastAPI"},
            {"text": "PostgreSQL"},
        ],
        tags=["python", "backend"],
        location="Tel Aviv",
        salary_min=15000,
        salary_max=25000,
        status=JobStatus.PUBLISHED,
    )
    defaults.update(overrides)
    async with TestSessionLocal() as s:
        job = Job(**defaults)
        s.add(job)
        await s.commit()
        await s.refresh(job)
        return job.id


async def _make_candidate_with_resume() -> int:
    async with TestSessionLocal() as s:
        c = CandidateProfile(
            full_name="Match Me",
            email="match@example.com",
            resume_path="uploads/resumes/match.docx",
            resume_filename="match.docx",
        )
        s.add(c)
        await s.commit()
        await s.refresh(c)
        return c.id


@pytest.mark.asyncio
async def test_embed_job_task_sets_embedding(company_profile, fake_embeddings):
    job_id = await _make_published_job(company_profile.id)
    with patch("rs_shared.core.matching.async_session", TestSessionLocal):
        await embed_job_task(job_id)

    async with TestSessionLocal() as s:
        job = await s.get(Job, job_id)
        assert job.embedding is not None
        assert len(job.embedding) == 1536


@pytest.mark.asyncio
async def test_embed_job_task_missing_job_is_noop(company_profile, fake_embeddings):
    with patch("rs_shared.core.matching.async_session", TestSessionLocal):
        await embed_job_task(999999)  # no exception


@pytest.mark.asyncio
async def test_match_candidate_task_embeds_resume_text(
    company_profile, fake_embeddings
):
    """Extracts and embeds the resume; the cosine-search itself is a live
    read-time query (see services.admin.candidates/jobs), not this task's job."""
    candidate_id = await _make_candidate_with_resume()
    resume_bytes = _make_resume_docx(
        "Experienced Python developer. FastAPI and PostgreSQL backend engineer."
    )
    storage = MagicMock()
    storage.download_file = AsyncMock(return_value=resume_bytes)

    with (
        patch("rs_shared.core.matching.async_session", TestSessionLocal),
        patch(
            "rs_shared.core.services.storage.get_storage_provider", return_value=storage
        ),
    ):
        await match_candidate_task(candidate_id)

    async with TestSessionLocal() as s:
        candidate = await s.get(CandidateProfile, candidate_id)
        assert candidate.parsed_text and "Python" in candidate.parsed_text
        assert candidate.embedding is not None
        assert len(candidate.embedding) == 1536


@pytest.mark.asyncio
async def test_match_candidate_task_recompute_is_idempotent(
    company_profile, fake_embeddings
):
    """Re-running on the same resume recomputes the same text/vector, not a
    duplicate or divergent one — important since SQS redelivers at least once."""
    candidate_id = await _make_candidate_with_resume()
    resume_bytes = _make_resume_docx("Python fastapi postgresql backend developer.")
    storage = MagicMock()
    storage.download_file = AsyncMock(return_value=resume_bytes)

    with (
        patch("rs_shared.core.matching.async_session", TestSessionLocal),
        patch(
            "rs_shared.core.services.storage.get_storage_provider", return_value=storage
        ),
    ):
        await match_candidate_task(candidate_id)
        async with TestSessionLocal() as s:
            first = await s.get(CandidateProfile, candidate_id)
            first_text, first_vec = first.parsed_text, list(first.embedding)

        await match_candidate_task(candidate_id)  # re-run

    async with TestSessionLocal() as s:
        second = await s.get(CandidateProfile, candidate_id)
        assert second.parsed_text == first_text
        assert list(second.embedding) == first_vec


@pytest.mark.asyncio
async def test_match_candidate_task_no_resume_is_noop(test_db, fake_embeddings):
    async with TestSessionLocal() as s:
        c = CandidateProfile(full_name="No Resume", email="nores@example.com")
        s.add(c)
        await s.commit()
        await s.refresh(c)
        candidate_id = c.id

    with patch("rs_shared.core.matching.async_session", TestSessionLocal):
        await match_candidate_task(candidate_id)  # no resume_path → no-op

    async with TestSessionLocal() as s:
        candidate = await s.get(CandidateProfile, candidate_id)
        assert candidate.parsed_text is None
        assert candidate.embedding is None


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("resume.PDF", "pdf"),
        ("uploads/resumes/a.b.docx", "docx"),
        ("no_extension", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_extension_of(name, expected):
    assert _extension_of(name) == expected


@pytest.mark.parametrize(
    ("distance", "expected"),
    [
        (1.0 - 0.28, 0.0),  # at the observed floor -> no match
        (1.0 - 0.62, 1.0),  # at the observed ceiling -> excellent match
        (1.0 - 0.45, (0.45 - 0.28) / (0.62 - 0.28)),  # linear in between
        (2.0, 0.0),  # opposite vectors clamp to 0
        (0.0, 1.0),  # identical vectors clamp to 1
    ],
)
def test_cosine_similarity_score_normalises_and_clamps(distance, expected):
    assert cosine_similarity_score(distance) == pytest.approx(expected)
