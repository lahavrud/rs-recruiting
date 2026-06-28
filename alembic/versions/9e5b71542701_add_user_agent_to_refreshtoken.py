"""add user_agent to refreshtoken

Revision ID: 9e5b71542701
Revises: db670081d5ed
Create Date: 2026-06-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9e5b71542701"
down_revision: str | None = "db670081d5ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "refreshtoken",
        sa.Column("user_agent", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("refreshtoken", "user_agent")
