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
    nightly_cleanup_task,
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
    # Still registered under the old key for EventBridge backward compat.
    assert "purge_expired_candidates" in TASK_REGISTRY
    assert TASK_REGISTRY["purge_expired_candidates"] is nightly_cleanup_task


# ---------------------------------------------------------------------------
# nightly_cleanup_task — OTel observability + dispatcher behaviour
# ---------------------------------------------------------------------------


def _patch_all_subtasks_returning(counts: dict[str, int]):
    """Patch all five sub-task coroutines to return the given counts."""
    base = "rs_shared.services.admin"
    return [
        patch(
            f"{base}._candidates_purge.purge_expired_candidates",
            new=AsyncMock(return_value=counts.get("purge_expired_candidates", 0)),
        ),
        patch(
            f"{base}.maintenance.purge_unactivated_candidate_users",
            new=AsyncMock(return_value=counts.get("purge_unactivated_users", 0)),
        ),
        patch(
            f"{base}.maintenance.purge_expired_data_export_zips",
            new=AsyncMock(return_value=counts.get("purge_export_zips", 0)),
        ),
        patch(
            f"{base}.maintenance.purge_expired_account_deletion_tokens",
            new=AsyncMock(return_value=counts.get("purge_deletion_tokens", 0)),
        ),
        patch(
            f"{base}.maintenance.purge_expired_activation_tokens",
            new=AsyncMock(return_value=counts.get("purge_activation_tokens", 0)),
        ),
    ]


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
async def test_nightly_cleanup_records_otel_metrics():
    purged_counter = MagicMock()
    unactivated_counter = MagicMock()
    export_counter = MagicMock()
    deletion_counter = MagicMock()
    activation_counter = MagicMock()
    gauge = MagicMock()

    counts = {
        "purge_expired_candidates": 3,
        "purge_unactivated_users": 2,
        "purge_export_zips": 5,
        "purge_deletion_tokens": 1,
        "purge_activation_tokens": 4,
    }
    s_patch, t_patch = _patch_session_noop()
    p0, p1, p2, p3, p4 = _patch_all_subtasks_returning(counts)
    with (
        p0,
        p1,
        p2,
        p3,
        p4,
        s_patch,
        t_patch,
        patch("rs_shared.core.tasks._purged_counter", purged_counter),
        patch("rs_shared.core.tasks._unactivated_users_counter", unactivated_counter),
        patch("rs_shared.core.tasks._export_zips_counter", export_counter),
        patch("rs_shared.core.tasks._deletion_tokens_counter", deletion_counter),
        patch("rs_shared.core.tasks._activation_tokens_counter", activation_counter),
        patch("rs_shared.core.tasks._last_purge_ran_gauge", gauge),
        patch("rs_shared.core.tasks.settings") as mock_settings,
    ):
        mock_settings.environment = "production"
        result = await nightly_cleanup_task()

    attrs = {"environment": "production"}
    assert result["purge_expired_candidates"] == 3
    assert result["purge_unactivated_users"] == 2
    purged_counter.add.assert_called_once_with(3, attrs)
    unactivated_counter.add.assert_called_once_with(2, attrs)
    export_counter.add.assert_called_once_with(5, attrs)
    deletion_counter.add.assert_called_once_with(1, attrs)
    activation_counter.add.assert_called_once_with(4, attrs)
    gauge.set.assert_called_once()


@pytest.mark.asyncio
async def test_nightly_cleanup_continues_after_subtask_failure():
    """A failing sub-task is logged and skipped; others still run."""
    s_patch, t_patch = _patch_session_noop()

    failing = AsyncMock(side_effect=RuntimeError("DB error"))
    succeeding = AsyncMock(return_value=7)

    with (
        patch(
            "rs_shared.services.admin._candidates_purge.purge_expired_candidates",
            new=failing,
        ),
        patch(
            "rs_shared.services.admin.maintenance.purge_unactivated_candidate_users",
            new=succeeding,
        ),
        patch(
            "rs_shared.services.admin.maintenance.purge_expired_data_export_zips",
            new=AsyncMock(return_value=0),
        ),
        patch(
            "rs_shared.services.admin.maintenance.purge_expired_account_deletion_tokens",
            new=AsyncMock(return_value=0),
        ),
        patch(
            "rs_shared.services.admin.maintenance.purge_expired_activation_tokens",
            new=AsyncMock(return_value=0),
        ),
        s_patch,
        t_patch,
        patch("rs_shared.core.tasks._purged_counter"),
        patch("rs_shared.core.tasks._unactivated_users_counter"),
        patch("rs_shared.core.tasks._export_zips_counter"),
        patch("rs_shared.core.tasks._deletion_tokens_counter"),
        patch("rs_shared.core.tasks._activation_tokens_counter"),
        patch("rs_shared.core.tasks._last_purge_ran_gauge"),
        patch("rs_shared.core.tasks.settings") as mock_settings,
    ):
        mock_settings.environment = "test"
        result = await nightly_cleanup_task()

    # Failed sub-task returns 0; succeeding sub-task returns its count.
    assert result["purge_expired_candidates"] == 0
    assert result["purge_unactivated_users"] == 7


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
