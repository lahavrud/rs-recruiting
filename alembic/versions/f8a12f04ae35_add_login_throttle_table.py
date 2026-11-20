"""add login_throttle table (per email + client IP failed-login state)

Revision ID: f8a12f04ae35
Revises: b8d1f04e37a2
Create Date: 2026-11-20 00:00:00.000000

Login lockout moves from the per-account ``user.failed_login_attempts`` /
``user.locked_until`` columns to this table, keyed by (email hash, client IP),
so a source that keeps failing is slowed down without locking the account's
owner out from elsewhere. Mirrors ``rs_shared.models.LoginThrottle``.

Expand-only: the old ``user`` columns are left in place so tasks still running
the previous release keep working during the rolling deploy. They are unused
from this release on and can be dropped in a later one.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "f8a12f04ae35"
down_revision: Union[str, None] = "b8d1f04e37a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_throttle",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("client_ip", sa.String(length=45), nullable=False),
        sa.Column("failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "email_hash",
            "client_ip",
            name="uq_login_throttle_email_hash_client_ip",
        ),
    )
    op.create_index(
        "ix_login_throttle_last_failure_at",
        "login_throttle",
        ["last_failure_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_login_throttle_last_failure_at", table_name="login_throttle")
    op.drop_table("login_throttle")
