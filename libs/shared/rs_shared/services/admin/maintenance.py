"""Nightly data-hygiene helpers.

Each function targets one class of stale rows and is designed to be called
from ``nightly_cleanup_task`` in ``rs_shared.core.tasks``. Each is
independently transacted so a failure in one sub-task does not roll back
the others.

All functions:
- Accept an open ``AsyncSession`` (caller supplies the transaction).
- Return the count of rows deleted.
- Emit structured log lines at INFO level (no PII).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.enums import UserRole
from rs_shared.models import (
    AccountDeletionToken,
    ActivationToken,
    DataExportRequest,
    User,
)

_logger = logging.getLogger(__name__)

_UNACTIVATED_USER_RETENTION_DAYS = 7
# Retain expired/used activation tokens this long for traceability.
_ACTIVATION_TOKEN_GRACE_DAYS = 30
# Retain used data-export ZIPs this long before sweeping.
_USED_EXPORT_GRACE_HOURS = 24


async def purge_unactivated_candidate_users(session: AsyncSession) -> int:
    """Delete CANDIDATE users who never activated within the 7-day window.

    Eligibility — all of:
    - ``User.role == CANDIDATE``
    - ``User.is_active == False``
    - ``User.created_at < now - 7 days``
    - No valid (unused + unexpired) ``ActivationToken`` still pending

    The User hard-delete cascades to RefreshToken, PasswordResetToken,
    ActivationToken, DataExportRequest, AccountDeletionToken rows. The FK on
    ``CandidateProfile.user_id`` is SET NULL, preserving the profile as an
    anonymous lead so Application history is not lost.

    Returns count of users deleted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=_UNACTIVATED_USER_RETENTION_DAYS
    )
    now = datetime.now(timezone.utc)

    # Users who still have a valid pending token are exempt.
    has_valid_token_subq = select(ActivationToken.user_id).where(
        ActivationToken.used == False,  # noqa: E712
        ActivationToken.expires_at > now,
    )

    eligible = list(
        (
            await session.execute(
                select(User).where(
                    User.role == UserRole.CANDIDATE,
                    User.is_active == False,  # noqa: E712
                    User.created_at < cutoff,
                    User.id.notin_(has_valid_token_subq),  # type: ignore[attr-defined]
                )
            )
        )
        .scalars()
        .all()
    )

    user_ids = [u.id for u in eligible]
    if user_ids:
        for uid in user_ids:
            _logger.info("cleanup.unactivated_user user_id=%d", uid)
        await session.execute(delete(User).where(User.id.in_(user_ids)))  # type: ignore[attr-defined]
        await session.flush()
        _logger.info(
            "purge_unactivated_candidate_users: removed %d users", len(user_ids)
        )
    return len(user_ids)


async def purge_expired_data_export_zips(session: AsyncSession) -> int:
    """Delete expired and stale-used DataExportRequest rows and their ZIPs.

    Eligibility:
    - ``expires_at < now`` (TTL elapsed), OR
    - ``used = true AND created_at < now - 24h`` (confirmed downloaded, grace elapsed)

    Storage deletion is best-effort: if the file cannot be deleted the row
    is preserved to avoid orphaning data in storage. A warning is logged.

    Returns count of rows deleted.
    """
    from rs_shared.core.services.storage import get_storage_provider

    now = datetime.now(timezone.utc)
    used_cutoff = now - timedelta(hours=_USED_EXPORT_GRACE_HOURS)

    rows = list(
        (
            await session.execute(
                select(DataExportRequest).where(
                    (DataExportRequest.expires_at < now)
                    | (
                        (DataExportRequest.used == True)  # noqa: E712
                        & (DataExportRequest.created_at < used_cutoff)
                    )
                )
            )
        )
        .scalars()
        .all()
    )

    storage = get_storage_provider()
    deleted = 0
    for row in rows:
        if row.download_path:
            try:
                await storage.delete_file(row.download_path)
            except Exception:
                _logger.warning(
                    "cleanup.export_zip_storage_error path=%s — skipping row",
                    row.download_path,
                )
                continue
        await session.delete(row)
        deleted += 1

    await session.flush()
    if deleted:
        _logger.info("purge_expired_data_export_zips: removed %d rows", deleted)
    return deleted


async def purge_expired_account_deletion_tokens(session: AsyncSession) -> int:
    """Delete expired or already-used AccountDeletionToken rows.

    Eligibility:
    - ``expires_at < now``, OR
    - ``used = true``

    Returns count of rows deleted.
    """
    now = datetime.now(timezone.utc)

    result = await session.execute(
        delete(AccountDeletionToken).where(
            (AccountDeletionToken.expires_at < now)
            | (AccountDeletionToken.used == True)  # noqa: E712
        )
    )
    count = result.rowcount
    if count:
        _logger.info("purge_expired_account_deletion_tokens: removed %d rows", count)
    return count


async def purge_expired_activation_tokens(session: AsyncSession) -> int:
    """Delete ActivationToken rows past the 30-day traceability window.

    Tokens are retained for 30 days after their ``expires_at`` so that
    activation attempts on stale links can still be attributed. After that
    they are noise.

    Eligibility: ``expires_at < now - 30 days``
    (covers both used and expired-but-unused tokens older than the window)

    Returns count of rows deleted.
    """
    threshold = datetime.now(timezone.utc) - timedelta(
        days=_ACTIVATION_TOKEN_GRACE_DAYS
    )

    result = await session.execute(
        delete(ActivationToken).where(ActivationToken.expires_at < threshold)
    )
    count = result.rowcount
    if count:
        _logger.info("purge_expired_activation_tokens: removed %d rows", count)
    return count
