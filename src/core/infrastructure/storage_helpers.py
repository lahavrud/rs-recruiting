"""Shared helpers for best-effort storage cleanup in service functions."""

from __future__ import annotations

from logging import Logger

from src.core.services.storage import StorageProvider


async def delete_file_best_effort(
    storage: StorageProvider,
    key: str,
    logger: Logger,
    context: str = "",
) -> None:
    """Delete a storage file, swallowing and logging any failure.

    Best-effort cleanup: callers use this when a storage delete is a
    secondary side effect (e.g. removing a stale file after a DB write
    already succeeded) and a storage outage must never block or fail the
    primary operation. Never re-raises.
    """
    try:
        await storage.delete_file(key)
    except Exception:
        if context:
            logger.exception("Failed to delete storage file %s: %s", key, context)
        else:
            logger.exception("Failed to delete storage file %s", key)
