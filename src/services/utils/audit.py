"""Audit log writes and queries.

`record_audit_event` is the single write helper used at sensitive admin
operations and system tasks. Callers invoke it inside their existing
`transactional()` block so the audit row commits atomically with the change
it records. `list_audit_events` powers the admin query endpoint.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.models import AuditLog
from src.schemas import AuditLogRead


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
            ip_address=ip_address,
            created_at=created_at or datetime.now(timezone.utc),
        )
    )
    await session.flush()


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
