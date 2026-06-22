"""Unit tests for the shared best-effort storage delete helper."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.infrastructure.storage_helpers import delete_file_best_effort


@pytest.mark.asyncio
async def test_delete_file_best_effort_calls_storage():
    storage = MagicMock()
    storage.delete_file = AsyncMock(return_value=True)
    logger = MagicMock(spec=logging.Logger)

    await delete_file_best_effort(storage, "some/key", logger)

    storage.delete_file.assert_awaited_once_with("some/key")
    logger.exception.assert_not_called()


@pytest.mark.asyncio
async def test_delete_file_best_effort_swallows_exception_and_logs():
    storage = MagicMock()
    storage.delete_file = AsyncMock(side_effect=RuntimeError("boom"))
    logger = MagicMock(spec=logging.Logger)

    # Should not raise.
    await delete_file_best_effort(storage, "some/key", logger)

    logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_delete_file_best_effort_includes_context_in_log():
    storage = MagicMock()
    storage.delete_file = AsyncMock(side_effect=RuntimeError("boom"))
    logger = MagicMock(spec=logging.Logger)

    await delete_file_best_effort(storage, "some/key", logger, context="remove_resume")

    args, _ = logger.exception.call_args
    assert "remove_resume" in args
