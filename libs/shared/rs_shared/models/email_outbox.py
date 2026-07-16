"""Transactional email outbox — the durable record of every email send.

A row is inserted in the *same transaction* as the domain change that triggers
the email (see ``core/tasks.py::queue_email``), so a committed approval can no
longer be followed by a silently-lost activation email: the row survives even
if the SQS nudge fails, and the sweeper re-enqueues it.

The row is also the idempotency key for the transport. SQS is at-least-once, so
``send_outbox_email_task`` guards every send on ``status`` — a redelivered
message for an already-``SENT`` row no-ops instead of re-emailing the recipient.

``status`` is Text rather than a native PG enum (the convention elsewhere in
this module) on purpose: this is internal machinery whose lifecycle is expected
to grow — bounce/suppression handling adds states — and migration
``bb83663b843e`` shows what widening a native enum costs here (rename the type,
recreate it, rewrite the column). ``EmailStatus`` is a ``str`` enum, so
``row.status == EmailStatus.SENT`` compares equal to the stored string either
way and the Python side stays typed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel

from rs_shared.enums import EmailStatus


class EmailOutbox(SQLModel, table=True):
    """One queued email: its full payload, delivery status, and send record."""

    __tablename__ = "email_outbox"
    __table_args__ = (
        # The sweeper's access path: rows stuck PENDING (SQS nudge never
        # landed) or SENDING (crashed mid-send) past a threshold.
        Index("ix_email_outbox_status_created_at", "status", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)

    # Business-level idempotency, opt-in per call site: a deterministic key for
    # the domain event (e.g. "password_reset:{token_id}") collapses the same
    # event enqueued twice. NULL means "no dedup" — Postgres permits unlimited
    # NULLs under a UNIQUE constraint, so most call sites simply omit it.
    dedup_key: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True, unique=True)
    )

    # Recipients are always stored as a list, even for the single-address case,
    # so the send path has one shape to handle.
    to_addrs: list[str] = Field(sa_column=Column(JSONB, nullable=False))
    subject: str = Field(sa_column=Column(Text, nullable=False))
    body: str = Field(sa_column=Column(Text, nullable=False))
    html_body: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # [[filename, base64_str, mimetype], ...] — the same wire shape as the SQS
    # transport encoding, so core/task_contract.py's encode/decode_attachments
    # are reused verbatim. Keeping the payload here (rather than in the SQS
    # body) also takes the 256KB SQS message ceiling off the attachment path.
    attachments: list | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    from_email: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    status: EmailStatus = Field(
        default=EmailStatus.PENDING,
        sa_column=Column(
            Text, nullable=False, server_default=EmailStatus.PENDING.value, index=True
        ),
    )
    attempts: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    # Provider-side id (SES MessageId). The answer to "did this actually go
    # out, and can support trace it?" — previously unanswerable.
    provider_message_id: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    sent_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
