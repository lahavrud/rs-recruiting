"""Audit-log model: append-only record of sensitive admin/system operations."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Text
from sqlmodel import Column, Field, SQLModel


class AuditLog(SQLModel, table=True):
    """Append-only record of sensitive admin operations and system tasks."""

    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)
    # No FK on actor_user_id: audit rows must outlive the user they reference
    # (deleting a user must not cascade-delete their audit history).
    actor_user_id: int | None = Field(default=None, index=True)
    action: str = Field(index=True, max_length=64)
    target_type: str = Field(index=True, max_length=64)
    target_id: int = Field(index=True)
    detail: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ip_address: str | None = Field(default=None, max_length=45)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
