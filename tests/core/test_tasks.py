"""Tests for SQS task producer and task implementations."""

import base64
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from docx import Document

from rs_shared.core.tasks import (
    TASK_REGISTRY,
    embed_job_task,
    enqueue_data_export_task,
    enqueue_email_task,
    match_candidate_task,
    purge_expired_candidate_data_task,
    send_email_task,
)
from rs_shared.enums import JobStatus
from rs_shared.models import CandidateProfile, Job
from tests.conftest import TestSessionLocal

# ---------------------------------------------------------------------------
# send_email_task — implementation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_email_task_success():
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    session_cm.__aexit__ = AsyncMock(return_value=None)
    txn_cm = MagicMock()
    txn_cm.__aenter__ = AsyncMock(return_value=None)
    txn_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("rs_shared.core.tasks.get_email_provider") as mock_get_provider,
        patch("rs_shared.core.tasks.async_session", return_value=session_cm),
        patch("rs_shared.core.tasks.transactional", return_value=txn_cm),
        patch("rs_shared.core.tasks.increment_and_alert", new_callable=AsyncMock),
    ):
        mock_provider = AsyncMock()
        mock_provider.send_email.return_value = True
        mock_get_provider.return_value = mock_provider

        result = await send_email_task(
            to="test@example.com",
            subject="Test Subject",
            body="Test Body",
        )

        assert result is True
        mock_provider.send_email.assert_called_once_with(
            to="test@example.com",
            subject="Test Subject",
            body="Test Body",
            html_body=None,
            attachments=None,
            from_email=None,
        )


@pytest.mark.asyncio
async def test_send_email_task_provider_returns_false_raises():
    with patch("rs_shared.core.tasks.get_email_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.send_email.return_value = False
        mock_get_provider.return_value = mock_provider

        with pytest.raises(RuntimeError, match="Email provider returned False"):
            await send_email_task(to="test@example.com", subject="Subject", body="Body")


@pytest.mark.asyncio
async def test_send_email_task_provider_exception_propagates():
    with patch("rs_shared.core.tasks.get_email_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.send_email.side_effect = Exception("SMTP connection failed")
        mock_get_provider.return_value = mock_provider

        with pytest.raises(Exception, match="SMTP connection failed"):
            await send_email_task(to="test@example.com", subject="Subject", body="Body")


# ---------------------------------------------------------------------------
# enqueue_email_task — inline path (SQS_QUEUE_URL not configured)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_email_task_inline_when_no_queue_url():
    """When SQS_QUEUE_URL is empty the task runs inline and returns 'inline'."""
    with (
        patch("rs_shared.core.tasks.settings") as mock_settings,
        patch(
            "rs_shared.core.tasks.send_email_task", new_callable=AsyncMock
        ) as mock_send,
    ):
        mock_settings.sqs_queue_url = ""
        mock_send.return_value = True

        result = await enqueue_email_task(
            to="test@example.com",
            subject="Subject",
            body="Body",
        )

    assert result == "inline"
    mock_send.assert_awaited_once_with(
        to="test@example.com",
        subject="Subject",
        body="Body",
        html_body=None,
        attachments=None,
        from_email=None,
    )


# ---------------------------------------------------------------------------
# enqueue_email_task — SQS path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_email_task_sends_to_sqs():
    """When SQS_QUEUE_URL is set, a message is sent and the MessageId returned."""
    with (
        patch("rs_shared.core.tasks.settings") as mock_settings,
        patch("rs_shared.core.tasks._sqs_send", new_callable=AsyncMock) as mock_sqs,
    ):
        mock_settings.sqs_queue_url = "https://sqs.us-east-1.amazonaws.com/123/queue"
        mock_sqs.return_value = "msg-id-abc"

        result = await enqueue_email_task(
            to="test@example.com",
            subject="Subject",
            body="Body",
        )

    assert result == "msg-id-abc"
    payload = mock_sqs.call_args[0][0]
    assert payload["task"] == "send_email"
    assert payload["to"] == "test@example.com"
    assert payload["attachments"] is None


@pytest.mark.asyncio
async def test_enqueue_email_task_base64_encodes_attachments():
    """Attachment bytes are base64-encoded for JSON-safe transport over SQS."""
    pdf_bytes = b"%PDF-1.4 fake pdf content"

    with (
        patch("rs_shared.core.tasks.settings") as mock_settings,
        patch("rs_shared.core.tasks._sqs_send", new_callable=AsyncMock) as mock_sqs,
    ):
        mock_settings.sqs_queue_url = "https://sqs.us-east-1.amazonaws.com/123/queue"
        mock_sqs.return_value = "msg-id-xyz"

        await enqueue_email_task(
            to="test@example.com",
            subject="Contract",
            body="See attached.",
            attachments=[("contract.pdf", pdf_bytes, "application/pdf")],
        )

    payload = mock_sqs.call_args[0][0]
    name, encoded, mime = payload["attachments"][0]
    assert name == "contract.pdf"
    assert mime == "application/pdf"
    assert base64.b64decode(encoded) == pdf_bytes


# ---------------------------------------------------------------------------
# enqueue_data_export_task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_data_export_task_sends_to_sqs():
    with (
        patch("rs_shared.core.tasks.settings") as mock_settings,
        patch("rs_shared.core.tasks._sqs_send", new_callable=AsyncMock) as mock_sqs,
    ):
        mock_settings.sqs_queue_url = "https://sqs.us-east-1.amazonaws.com/123/queue"
        mock_sqs.return_value = "export-msg-id"

        result = await enqueue_data_export_task(user_id=42)

    assert result == "export-msg-id"
    payload = mock_sqs.call_args[0][0]
    assert payload == {"task": "build_data_export", "user_id": 42}


# ---------------------------------------------------------------------------
# TASK_REGISTRY — completeness
# ---------------------------------------------------------------------------


def test_task_registry_contains_expected_tasks():
    assert "send_email" in TASK_REGISTRY
    assert "build_data_export" in TASK_REGISTRY
    assert "purge_expired_candidates" in TASK_REGISTRY


# ---------------------------------------------------------------------------
# purge_expired_candidate_data_task — OTel observability
# ---------------------------------------------------------------------------


def _patch_purge_returning(count: int):
    return patch(
        "rs_shared.services.admin.candidates.purge_expired_candidates",
        new=AsyncMock(return_value=count),
    )


def _patch_session_noop():
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    session_cm.__aexit__ = AsyncMock(return_value=None)

    txn_cm = MagicMock()
    txn_cm.__aenter__ = AsyncMock(return_value=None)
    txn_cm.__aexit__ = AsyncMock(return_value=None)

    return (
        patch("rs_shared.core.tasks.async_session", return_value=session_cm),
        patch("rs_shared.core.tasks.transactional", return_value=txn_cm),
    )


@pytest.mark.asyncio
async def test_purge_task_records_otel_metrics():
    counter = MagicMock()
    gauge = MagicMock()
    s_patch, t_patch = _patch_session_noop()
    with (
        _patch_purge_returning(7),
        s_patch,
        t_patch,
        patch("rs_shared.core.tasks._purged_counter", counter),
        patch("rs_shared.core.tasks._last_purge_ran_gauge", gauge),
        patch("rs_shared.core.tasks.settings") as mock_settings,
    ):
        mock_settings.environment = "prod"
        result = await purge_expired_candidate_data_task()

    assert result == 7
    counter.add.assert_called_once_with(7, {"environment": "prod"})
    gauge.set.assert_called_once()
    _, attrs = gauge.set.call_args[0]
    assert attrs == {"environment": "prod"}


@pytest.mark.asyncio
async def test_purge_task_records_zero_count():
    counter = MagicMock()
    gauge = MagicMock()
    s_patch, t_patch = _patch_session_noop()
    with (
        _patch_purge_returning(0),
        s_patch,
        t_patch,
        patch("rs_shared.core.tasks._purged_counter", counter),
        patch("rs_shared.core.tasks._last_purge_ran_gauge", gauge),
        patch("rs_shared.core.tasks.settings") as mock_settings,
    ):
        mock_settings.environment = "prod"
        result = await purge_expired_candidate_data_task()

    assert result == 0
    counter.add.assert_called_once_with(0, {"environment": "prod"})
    gauge.set.assert_called_once()


@pytest.mark.asyncio
async def test_purge_task_returns_count_in_all_environments():
    s_patch, t_patch = _patch_session_noop()
    with (
        _patch_purge_returning(3),
        s_patch,
        t_patch,
        patch("rs_shared.core.tasks._purged_counter"),
        patch("rs_shared.core.tasks._last_purge_ran_gauge"),
        patch("rs_shared.core.tasks.settings") as mock_settings,
    ):
        mock_settings.environment = "dev"
        result = await purge_expired_candidate_data_task()

    assert result == 3


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


def test_matching_tasks_registered():
    assert TASK_REGISTRY["embed_job"] is embed_job_task
    assert TASK_REGISTRY["match_candidate"] is match_candidate_task
