"""Tests for the email outbox: durability, idempotency, and the send record.

These run against the real test database rather than a mocked session — the
whole point of the outbox is what survives a commit, which a MagicMock session
cannot demonstrate.
"""

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from rs_shared.core.services import email_outbox
from rs_shared.core.tasks import send_outbox_email_task, sweep_email_outbox_task
from rs_shared.enums import EmailStatus
from rs_shared.models import EmailOutbox


@pytest.fixture
def outbox_db(session_local_factory):
    """Point the task's own async_session at the test database.

    send_outbox_email_task opens its own sessions (it runs in the worker, not a
    request), so the test DB has to be injected at that seam.
    """
    with patch("rs_shared.core.tasks.async_session", session_local_factory):
        yield


@pytest.fixture
def fake_provider():
    """A provider that reports success without touching the network."""
    provider = AsyncMock()
    provider.send_email.return_value = True
    with patch("rs_shared.core.tasks.get_email_provider", return_value=provider):
        yield provider


async def _queue_row(session, **overrides) -> int:
    """Insert a PENDING row and commit it, as a service call site would."""
    kwargs = {
        "to": "candidate@test.com",
        "subject": "נושא",
        "body": "גוף ההודעה",
        **overrides,
    }
    outbox_id = await email_outbox.insert_email(session, **kwargs)
    await session.commit()
    return outbox_id


async def _get(session, outbox_id: int) -> EmailOutbox:
    row = (
        await session.execute(select(EmailOutbox).where(EmailOutbox.id == outbox_id))
    ).scalar_one()
    await session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Happy path — the send record
# ---------------------------------------------------------------------------


async def test_send_marks_row_sent_and_records_when(session, outbox_db, fake_provider):
    outbox_id = await _queue_row(session)

    sent = await send_outbox_email_task(outbox_id)

    assert sent is True
    fake_provider.send_email.assert_called_once()
    row = await _get(session, outbox_id)
    assert row.status == EmailStatus.SENT
    assert row.sent_at is not None
    assert row.attempts == 1


async def test_send_normalizes_single_recipient_to_a_list(
    session, outbox_db, fake_provider
):
    outbox_id = await _queue_row(session, to="one@test.com")

    await send_outbox_email_task(outbox_id)

    assert fake_provider.send_email.call_args.kwargs["to"] == ["one@test.com"]


# ---------------------------------------------------------------------------
# Idempotency — SQS is at-least-once
# ---------------------------------------------------------------------------


async def test_redelivery_of_a_sent_row_does_not_send_again(
    session, outbox_db, fake_provider
):
    outbox_id = await _queue_row(session)

    first = await send_outbox_email_task(outbox_id)
    second = await send_outbox_email_task(outbox_id)  # SQS redelivers

    assert first is True
    assert second is False
    assert fake_provider.send_email.call_count == 1


async def test_quota_failure_does_not_cause_a_duplicate_send(
    session, outbox_db, fake_provider
):
    """The regression this outbox was built for.

    The quota bump used to run in its own transaction *after* a successful
    send. When it failed, the exception propagated, SQS redelivered, and the
    recipient got the email twice. The bump now shares the mark-sent
    transaction, so a failure leaves the row in SENDING — which the claim
    guard refuses to resend.
    """
    outbox_id = await _queue_row(session)

    with patch(
        "rs_shared.core.services.email_outbox.increment_and_alert",
        new_callable=AsyncMock,
        side_effect=RuntimeError("quota table unavailable"),
    ):
        with pytest.raises(RuntimeError, match="quota table unavailable"):
            await send_outbox_email_task(outbox_id)

    assert fake_provider.send_email.call_count == 1
    row = await _get(session, outbox_id)
    assert row.status == EmailStatus.SENDING

    # The redelivery that used to double-send.
    resent = await send_outbox_email_task(outbox_id)

    assert resent is False
    assert fake_provider.send_email.call_count == 1


async def test_dedup_key_collapses_the_same_event_queued_twice(session):
    first = await _queue_row(session, dedup_key="job_closed:42")
    second = await _queue_row(session, dedup_key="job_closed:42")

    assert first is not None
    assert second is None

    rows = (
        (
            await session.execute(
                select(EmailOutbox).where(EmailOutbox.dedup_key == "job_closed:42")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


async def test_rows_without_a_dedup_key_never_collide(session):
    first = await _queue_row(session)
    second = await _queue_row(session)

    assert first != second
    assert second is not None


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


async def test_transient_failure_returns_row_to_pending_and_raises(session, outbox_db):
    outbox_id = await _queue_row(session)
    provider = AsyncMock()
    provider.send_email.side_effect = RuntimeError("SES throttled")

    with patch("rs_shared.core.tasks.get_email_provider", return_value=provider):
        with pytest.raises(RuntimeError, match="SES throttled"):
            await send_outbox_email_task(outbox_id)

    row = await _get(session, outbox_id)
    assert row.status == EmailStatus.PENDING  # claimable again on redelivery
    assert row.attempts == 1
    assert "SES throttled" in row.last_error


async def test_provider_returning_false_is_treated_as_a_failure(session, outbox_db):
    outbox_id = await _queue_row(session)
    provider = AsyncMock()
    provider.send_email.return_value = False

    with patch("rs_shared.core.tasks.get_email_provider", return_value=provider):
        with pytest.raises(RuntimeError, match="returned False"):
            await send_outbox_email_task(outbox_id)

    row = await _get(session, outbox_id)
    assert row.status == EmailStatus.PENDING


async def test_row_is_parked_as_failed_once_attempts_are_exhausted(session, outbox_db):
    outbox_id = await _queue_row(session)
    row = await _get(session, outbox_id)
    row.attempts = email_outbox.MAX_SEND_ATTEMPTS
    await session.commit()

    provider = AsyncMock()
    provider.send_email.side_effect = RuntimeError("still failing")

    with patch("rs_shared.core.tasks.get_email_provider", return_value=provider):
        # No raise — the message is done being retried.
        result = await send_outbox_email_task(outbox_id)

    assert result is False
    row = await _get(session, outbox_id)
    assert row.status == EmailStatus.FAILED
    assert "still failing" in row.last_error


async def test_a_failed_row_is_never_picked_up_again(session, outbox_db, fake_provider):
    outbox_id = await _queue_row(session)
    row = await _get(session, outbox_id)
    row.status = EmailStatus.FAILED
    await session.commit()

    result = await send_outbox_email_task(outbox_id)

    assert result is False
    fake_provider.send_email.assert_not_called()


async def test_missing_row_is_a_no_op(session, outbox_db, fake_provider):
    result = await send_outbox_email_task(999999)

    assert result is False
    fake_provider.send_email.assert_not_called()


# ---------------------------------------------------------------------------
# Sweeper — the backstop for a failed SQS nudge
# ---------------------------------------------------------------------------


async def test_sweeper_requeues_a_row_whose_nudge_never_landed(session, outbox_db):
    """The silent-loss path: enqueue failed, but the row is committed."""
    outbox_id = await _queue_row(session)
    row = await _get(session, outbox_id)
    row.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await session.commit()

    with patch(
        "rs_shared.core.tasks.enqueue_send_outbox_email_task", new_callable=AsyncMock
    ) as mock_enqueue:
        result = await sweep_email_outbox_task()

    assert result["requeued"] == 1
    mock_enqueue.assert_called_once_with(outbox_id)


async def test_sweeper_leaves_fresh_pending_rows_alone(session, outbox_db):
    await _queue_row(session)

    with patch(
        "rs_shared.core.tasks.enqueue_send_outbox_email_task", new_callable=AsyncMock
    ) as mock_enqueue:
        result = await sweep_email_outbox_task()

    assert result["requeued"] == 0
    mock_enqueue.assert_not_called()


async def test_sweeper_leaves_a_just_retried_row_to_its_redelivery(session, outbox_db):
    """A retried row is old by created_at but fresh by updated_at.

    mark_for_retry returns it to PENDING without touching created_at, so a
    sweeper keyed on creation time would re-nudge it on every pass and race
    the SQS redelivery that is already coming.
    """
    outbox_id = await _queue_row(session)
    row = await _get(session, outbox_id)
    row.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await email_outbox.mark_for_retry(session, row, "SMTP timeout")
    await session.commit()

    with patch(
        "rs_shared.core.tasks.enqueue_send_outbox_email_task", new_callable=AsyncMock
    ) as mock_enqueue:
        result = await sweep_email_outbox_task()

    assert result["requeued"] == 0
    mock_enqueue.assert_not_called()


async def test_sweeper_reports_stuck_sending_rows_without_resending(session, outbox_db):
    """A SENDING row may already be in the recipient's inbox — never resend it."""
    outbox_id = await _queue_row(session)
    row = await _get(session, outbox_id)
    row.status = EmailStatus.SENDING
    row.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await session.commit()

    with patch(
        "rs_shared.core.tasks.enqueue_send_outbox_email_task", new_callable=AsyncMock
    ) as mock_enqueue:
        result = await sweep_email_outbox_task()

    assert result["stuck_sending"] == 1
    assert result["requeued"] == 0
    mock_enqueue.assert_not_called()


# ---------------------------------------------------------------------------
# Concurrent claims — routine contention must not page anyone
# ---------------------------------------------------------------------------


async def test_a_send_still_in_flight_is_skipped_without_a_critical(session, caplog):
    """SENDING + recently touched is another worker mid-send, not a crash.

    An at-least-once duplicate lands here routinely. Paging on it would train
    everyone to ignore outbox_row_stuck_sending, which is the one log that
    means an email may really have been lost.
    """
    outbox_id = await _queue_row(session)
    row = await _get(session, outbox_id)
    row.status = EmailStatus.SENDING
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()

    with caplog.at_level(logging.WARNING):
        assert await email_outbox.claim_for_send(session, outbox_id) is None

    events = {r.getMessage() for r in caplog.records}
    assert "outbox_send_skipped_in_flight" in events
    assert "outbox_row_stuck_sending" not in events


async def test_a_send_stalled_past_the_sweep_threshold_is_critical(session, caplog):
    outbox_id = await _queue_row(session)
    row = await _get(session, outbox_id)
    row.status = EmailStatus.SENDING
    row.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await session.commit()

    with caplog.at_level(logging.WARNING):
        assert await email_outbox.claim_for_send(session, outbox_id) is None

    critical = [r.getMessage() for r in caplog.records if r.levelno == logging.CRITICAL]
    assert critical == ["outbox_row_stuck_sending"]
