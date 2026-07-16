"""add_email_outbox_table

Transactional email outbox: durable per-email row written in the same
transaction as the domain change, and the idempotency guard for SQS
redelivery. See libs/shared/rs_shared/models/email_outbox.py.

Additive only — no backfill. Existing in-flight `send_email` SQS messages are
unaffected; they keep using the legacy path for one release.

Revision ID: c4a1e9b7d38f
Revises: 29333542be15
Create Date: 2026-07-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4a1e9b7d38f"
down_revision: Union[str, Sequence[str], None] = "29333542be15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dedup_key", sa.Text(), nullable=True),
        sa.Column("to_addrs", postgresql.JSONB(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=True),
        sa.Column("attachments", postgresql.JSONB(), nullable=True),
        sa.Column("from_email", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedup_key"),
    )
    # Serves both the sweeper's (status, created_at) scan and any status-only
    # lookup via its leftmost prefix — no separate index on status alone.
    op.create_index(
        "ix_email_outbox_status_created_at", "email_outbox", ["status", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_email_outbox_status_created_at", table_name="email_outbox")
    op.drop_table("email_outbox")
