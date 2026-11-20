"""Tests for the email-sending task implementations (core/email_tasks.py)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rs_shared.core.email_tasks import send_email_task

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
        patch("rs_shared.core.email_tasks.get_email_provider") as mock_get_provider,
        patch("rs_shared.core.email_tasks.async_session", return_value=session_cm),
        patch("rs_shared.core.email_tasks.transactional", return_value=txn_cm),
        patch("rs_shared.core.email_tasks.increment_and_alert", new_callable=AsyncMock),
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
    with patch("rs_shared.core.email_tasks.get_email_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.send_email.return_value = False
        mock_get_provider.return_value = mock_provider

        with pytest.raises(RuntimeError, match="Email provider returned False"):
            await send_email_task(to="test@example.com", subject="Subject", body="Body")


@pytest.mark.asyncio
async def test_send_email_task_provider_exception_propagates():
    with patch("rs_shared.core.email_tasks.get_email_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.send_email.side_effect = Exception("SMTP connection failed")
        mock_get_provider.return_value = mock_provider

        with pytest.raises(Exception, match="SMTP connection failed"):
            await send_email_task(to="test@example.com", subject="Subject", body="Body")
