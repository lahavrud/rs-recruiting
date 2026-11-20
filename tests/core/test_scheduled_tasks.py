"""Tests for the nightly cleanup and admin digest tasks (core/scheduled_tasks.py)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rs_shared.core.scheduled_tasks import nightly_cleanup_task, send_admin_digest_task

# ---------------------------------------------------------------------------
# send_admin_digest_task — scheduled daily digest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_admin_digest_task_runs_the_digest_in_its_own_transaction(
    session_local_factory,
):
    digest = AsyncMock(return_value=3)
    with (
        patch("rs_shared.core.scheduled_tasks.async_session", session_local_factory),
        patch(
            "rs_shared.services.admin.application_digest.send_application_digest",
            digest,
        ),
    ):
        assert await send_admin_digest_task() == 3

    digest.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_admin_digest_task_propagates_failures(session_local_factory):
    """A swallowed error would ack the SQS message and silently skip the day."""
    with (
        patch("rs_shared.core.scheduled_tasks.async_session", session_local_factory),
        patch(
            "rs_shared.services.admin.application_digest.send_application_digest",
            AsyncMock(side_effect=RuntimeError("db down")),
        ),
        pytest.raises(RuntimeError, match="db down"),
    ):
        await send_admin_digest_task()


# ---------------------------------------------------------------------------
# nightly_cleanup_task — OTel observability + dispatcher behaviour
# ---------------------------------------------------------------------------


def _patch_all_subtasks_returning(counts: dict[str, int]):
    """Patch every sub-task coroutine to return the given counts."""
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
        patch(
            f"{base}.maintenance.redact_expired_email_outbox",
            new=AsyncMock(return_value=counts.get("redact_email_outbox", 0)),
        ),
        patch(
            f"{base}.maintenance.purge_expired_email_outbox",
            new=AsyncMock(return_value=counts.get("purge_email_outbox", 0)),
        ),
        patch(
            f"{base}.maintenance.purge_expired_login_throttle",
            new=AsyncMock(return_value=counts.get("purge_login_throttle", 0)),
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
        patch("rs_shared.core.scheduled_tasks.async_session", return_value=session_cm),
        patch("rs_shared.core.scheduled_tasks.transactional", return_value=txn_cm),
    )


@pytest.mark.asyncio
async def test_nightly_cleanup_records_otel_metrics():
    purged_counter = MagicMock()
    unactivated_counter = MagicMock()
    export_counter = MagicMock()
    deletion_counter = MagicMock()
    activation_counter = MagicMock()
    outbox_redacted_counter = MagicMock()
    outbox_purged_counter = MagicMock()
    login_throttle_counter = MagicMock()
    gauge = MagicMock()

    counts = {
        "purge_expired_candidates": 3,
        "purge_unactivated_users": 2,
        "purge_export_zips": 5,
        "purge_deletion_tokens": 1,
        "purge_activation_tokens": 4,
        "redact_email_outbox": 6,
        "purge_email_outbox": 8,
        "purge_login_throttle": 9,
    }
    s_patch, t_patch = _patch_session_noop()
    p0, p1, p2, p3, p4, p5, p6, p7 = _patch_all_subtasks_returning(counts)
    with (
        p0,
        p1,
        p2,
        p3,
        p4,
        p5,
        p6,
        p7,
        s_patch,
        t_patch,
        patch("rs_shared.core.scheduled_tasks._purged_counter", purged_counter),
        patch(
            "rs_shared.core.scheduled_tasks._unactivated_users_counter",
            unactivated_counter,
        ),
        patch("rs_shared.core.scheduled_tasks._export_zips_counter", export_counter),
        patch(
            "rs_shared.core.scheduled_tasks._deletion_tokens_counter", deletion_counter
        ),
        patch(
            "rs_shared.core.scheduled_tasks._activation_tokens_counter",
            activation_counter,
        ),
        patch(
            "rs_shared.core.scheduled_tasks._outbox_redacted_counter",
            outbox_redacted_counter,
        ),
        patch(
            "rs_shared.core.scheduled_tasks._outbox_purged_counter",
            outbox_purged_counter,
        ),
        patch(
            "rs_shared.core.scheduled_tasks._login_throttle_purged_counter",
            login_throttle_counter,
        ),
        patch("rs_shared.core.scheduled_tasks._last_purge_ran_gauge", gauge),
        patch("rs_shared.core.scheduled_tasks.settings") as mock_settings,
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
    outbox_redacted_counter.add.assert_called_once_with(6, attrs)
    outbox_purged_counter.add.assert_called_once_with(8, attrs)
    login_throttle_counter.add.assert_called_once_with(9, attrs)
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
        patch(
            "rs_shared.services.admin.maintenance.redact_expired_email_outbox",
            new=AsyncMock(return_value=0),
        ),
        patch(
            "rs_shared.services.admin.maintenance.purge_expired_email_outbox",
            new=AsyncMock(return_value=0),
        ),
        patch(
            "rs_shared.services.admin.maintenance.purge_expired_login_throttle",
            new=AsyncMock(return_value=0),
        ),
        s_patch,
        t_patch,
        patch("rs_shared.core.scheduled_tasks._purged_counter"),
        patch("rs_shared.core.scheduled_tasks._unactivated_users_counter"),
        patch("rs_shared.core.scheduled_tasks._export_zips_counter"),
        patch("rs_shared.core.scheduled_tasks._deletion_tokens_counter"),
        patch("rs_shared.core.scheduled_tasks._activation_tokens_counter"),
        patch("rs_shared.core.scheduled_tasks._outbox_redacted_counter"),
        patch("rs_shared.core.scheduled_tasks._outbox_purged_counter"),
        patch("rs_shared.core.scheduled_tasks._login_throttle_purged_counter"),
        patch("rs_shared.core.scheduled_tasks._last_purge_ran_gauge"),
        patch("rs_shared.core.scheduled_tasks.settings") as mock_settings,
    ):
        mock_settings.environment = "test"
        result = await nightly_cleanup_task()

    # A failed sub-task records None — distinct from 0, which means "ran and
    # purged nothing". Succeeding sub-tasks still return their count.
    assert result["purge_expired_candidates"] is None
    assert result["purge_unactivated_users"] == 7
