"""Audit log writes and queries.

`record_audit_event` is the single write helper used at sensitive admin
operations and system tasks. Callers invoke it inside their existing
`transactional()` block so the audit row commits atomically with the change
it records. `list_audit_events` powers the admin query endpoint.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from rs_shared.models import AuditLog
from rs_shared.schemas import AuditLogRead

_logger = logging.getLogger(__name__)

# AuditLog.ip_address is String(45), the longest IPv6 text form. client_ip()
# can pass through a raw forwarded value from a trusted proxy; an over-long one
# must not fail the write (and with it the change being recorded).
_IP_MAX_LEN = 45


async def record_audit_event(
    session: AsyncSession,
    *,
    actor_user_id: int | None,
    action: str,
    target_type: str,
    target_id: int,
    detail: str | None = None,
    ip_address: str | None = None,
    created_at: datetime | None = None,
) -> None:
    """Append one audit row. Must be called inside a transactional block.

    `created_at` defaults to now; callers can backdate it (e.g. seed scripts
    building realistic history).
    """
    session.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=ip_address[:_IP_MAX_LEN] if ip_address else ip_address,
            created_at=created_at or datetime.now(timezone.utc),
        )
    )
    await session.flush()


async def record_audit_event_best_effort(
    session: AsyncSession,
    *,
    actor_user_id: int | None,
    action: str,
    target_type: str,
    target_id: int,
    ip_address: str | None = None,
) -> None:
    """Audit a security action without letting the audit write undo it.

    For the writers that commit their own session alongside a security control
    (the refresh-token nuke on replay, the failed-login throttle count): the
    row goes in a SAVEPOINT, so if it fails only the row is lost and logged,
    and the caller's commit still applies the control.
    """
    try:
        async with session.begin_nested():
            await record_audit_event(
                session,
                actor_user_id=actor_user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                ip_address=ip_address,
            )
    except Exception:
        _logger.exception(
            "audit_write_failed", extra={"action": action, "target_id": target_id}
        )


async def list_audit_events(
    session: AsyncSession,
    *,
    target_type: str | None = None,
    target_id: int | None = None,
    actor_user_id: int | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[AuditLogRead]:
    """One page of audit events, newest first, with optional filters."""
    page_size = clamp_limit(limit)
    base = select(AuditLog)
    if target_type is not None:
        base = base.where(AuditLog.target_type == target_type)  # pyright: ignore[reportArgumentType]
    if target_id is not None:
        base = base.where(AuditLog.target_id == target_id)  # pyright: ignore[reportArgumentType]
    if actor_user_id is not None:
        base = base.where(AuditLog.actor_user_id == actor_user_id)  # pyright: ignore[reportArgumentType]
    if from_dt is not None:
        base = base.where(AuditLog.created_at >= from_dt)  # pyright: ignore[reportArgumentType]
    if to_dt is not None:
        base = base.where(AuditLog.created_at <= to_dt)  # pyright: ignore[reportArgumentType]

    query = apply_cursor(
        base,
        sort_col=AuditLog.created_at,  # pyright: ignore[reportArgumentType]
        id_col=AuditLog.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
    )
    rows = list((await session.execute(query)).scalars().all())
    return build_cursor_page(
        rows,
        serializer=AuditLogRead.model_validate,
        cursor_key=lambda a: (a.created_at, a.id),
        limit=page_size,
    )


def changed_fields(target: object, updates: dict[str, object]) -> list[str]:
    """Sorted names of the ``updates`` keys whose value differs on ``target``.

    For update audits: call it *before* applying the changes, and record
    ``fields_detail(...)``. Names only, never values: the fields being edited
    (application answers, contact details) can hold personal data, and the
    audit log outlives the data it describes.
    """
    return sorted(k for k, v in updates.items() if getattr(target, k, None) != v)


def fields_detail(fields: list[str]) -> str:
    return "fields=" + ",".join(fields)
