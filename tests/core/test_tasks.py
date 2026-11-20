"""Tests for SQS task producer and task implementations."""

import base64
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from rs_shared.core.tasks import (
    TASK_REGISTRY,
    build_data_export_task,
    embed_job_task,
    enqueue_data_export_task,
    enqueue_email_task,
    match_candidate_task,
    nightly_cleanup_task,
    send_admin_digest_task,
)
from rs_shared.enums import EmailStatus, UserRole
from rs_shared.models import (
    CandidateProfile,
    DataExportRequest,
    EmailOutbox,
    User,
)
from rs_shared.services.candidate.data_export import has_pending_export

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
# build_data_export_task — implementation
# ---------------------------------------------------------------------------


async def _seed_export_candidate(session, email: str) -> User:
    user = User(
        email=email,
        hashed_password="hashed",  # pragma: allowlist secret
        role=UserRole.CANDIDATE,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    session.add(
        CandidateProfile(
            user_id=user.id,
            full_name="Export Me",
            email=email,
            phone="050-000-0001",
        )
    )
    await session.commit()
    return user


def _fake_export_storage() -> MagicMock:
    storage = MagicMock()
    storage.upload_file = AsyncMock(return_value="exports/1/export.zip")
    storage.download_file = AsyncMock(return_value=b"resume-bytes")
    storage.delete_file = AsyncMock(return_value=True)
    return storage


@pytest.mark.asyncio
async def test_build_data_export_task_notify_failure_leaves_no_pending_export(
    session, session_local_factory
):
    """A failed notify must not strand the export behind the idempotency guard.

    The unused ``DataExportRequest`` row IS the idempotency guard (see
    rules/worker.md) and the API's 429 rate limit. If it survives a failed
    notification the candidate never gets the link, redelivery no-ops on the
    guard, and `has_pending_export` locks them out for DATA_EXPORT_TTL_HOURS.
    Redelivery must be able to rebuild, so the row must not outlive the failure.

    The outbox row is written in the export's own transaction, so this now
    holds by rollback rather than by an explicit discard.
    """
    user = await _seed_export_candidate(session, "strand@test.com")
    storage = _fake_export_storage()

    with (
        patch("rs_shared.core.tasks.async_session", session_local_factory),
        patch(
            "rs_shared.core.services.storage.get_storage_provider",
            return_value=storage,
        ),
        patch("rs_shared.core.tasks.queue_email", new_callable=AsyncMock) as mock_email,
    ):
        mock_email.side_effect = RuntimeError("outbox insert failed")

        # Must propagate: a swallowed exception acks the message and loses the work.
        with pytest.raises(RuntimeError):
            await build_data_export_task(user.id)

    async with session_local_factory() as fresh:
        assert await has_pending_export(user.id, fresh) is False


@pytest.mark.asyncio
async def test_build_data_export_task_redelivery_recovers_after_notify_failure(
    session, session_local_factory
):
    """The point of rolling the export back: the SQS retry must actually succeed.

    Reproduces the real sequence — the queue write fails, the message is
    redelivered, and the second attempt rebuilds and emails rather than
    no-opping on a guard row left behind by the first.
    """
    user = await _seed_export_candidate(session, "retry@test.com")
    storage = _fake_export_storage()

    with (
        patch("rs_shared.core.tasks.async_session", session_local_factory),
        patch(
            "rs_shared.core.services.storage.get_storage_provider",
            return_value=storage,
        ),
        patch("rs_shared.core.tasks.queue_email", new_callable=AsyncMock) as mock_email,
    ):
        mock_email.side_effect = RuntimeError("outbox insert failed")
        with pytest.raises(RuntimeError):
            await build_data_export_task(user.id)

        # SQS redelivers the same message; this time the queue write succeeds.
        mock_email.side_effect = None
        await build_data_export_task(user.id)

    assert mock_email.await_count == 2
    assert mock_email.await_args.kwargs["to"] == "retry@test.com"
    async with session_local_factory() as fresh:
        assert await has_pending_export(user.id, fresh) is True


@pytest.mark.asyncio
async def test_build_data_export_task_succeeds_and_keeps_the_export(
    session, session_local_factory
):
    """The happy path: the export row and its notification commit together.

    Uses the real ``queue_email`` and reads back from a fresh session, so this
    fails if the outbox row is written to a transaction nobody commits — the
    exact silent loss the outbox exists to prevent.
    """
    user = await _seed_export_candidate(session, "happy@test.com")
    storage = _fake_export_storage()

    with (
        patch("rs_shared.core.tasks.async_session", session_local_factory),
        patch(
            "rs_shared.core.services.storage.get_storage_provider",
            return_value=storage,
        ),
        patch(
            "rs_shared.core.tasks.enqueue_send_outbox_email_task",
            new_callable=AsyncMock,
        ),
    ):
        await build_data_export_task(user.id)

    storage.delete_file.assert_not_awaited()
    async with session_local_factory() as fresh:
        assert await has_pending_export(user.id, fresh) is True
        row = (await fresh.execute(select(EmailOutbox))).scalars().one()
        assert row.to_addrs == ["happy@test.com"]
        assert row.status == EmailStatus.PENDING


@pytest.mark.asyncio
async def test_build_data_export_task_noops_when_pending_export_exists(
    session, session_local_factory
):
    """The at-least-once guard still holds: a real duplicate is a no-op."""
    user = await _seed_export_candidate(session, "dupe@test.com")
    session.add(
        DataExportRequest(
            token_hash="h",
            user_id=user.id,
            download_path="exports/existing.zip",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    await session.commit()
    storage = _fake_export_storage()

    with (
        patch("rs_shared.core.tasks.async_session", session_local_factory),
        patch(
            "rs_shared.core.services.storage.get_storage_provider",
            return_value=storage,
        ),
        patch(
            "rs_shared.core.tasks.enqueue_email_task", new_callable=AsyncMock
        ) as mock_email,
    ):
        await build_data_export_task(user.id)

    storage.upload_file.assert_not_awaited()
    mock_email.assert_not_awaited()


# ---------------------------------------------------------------------------
# TASK_REGISTRY — completeness
# ---------------------------------------------------------------------------


def test_task_registry_contains_expected_tasks():
    assert "send_email" in TASK_REGISTRY
    assert "build_data_export" in TASK_REGISTRY
    # Still registered under the old key for EventBridge backward compat.
    assert "purge_expired_candidates" in TASK_REGISTRY
    assert TASK_REGISTRY["purge_expired_candidates"] is nightly_cleanup_task
    # EventBridge Scheduler (rs-recruiting-infra, modules/sqs) sends this key.
    assert TASK_REGISTRY["send_admin_digest"] is send_admin_digest_task


def test_matching_tasks_registered():
    assert TASK_REGISTRY["embed_job"] is embed_job_task
    assert TASK_REGISTRY["match_candidate"] is match_candidate_task
