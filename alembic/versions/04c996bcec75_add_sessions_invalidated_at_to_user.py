"""add_sessions_invalidated_at_to_user

Revision ID: 04c996bcec75
Revises: 9e5b71542701
Create Date: 2026-06-28 14:18:13.085645

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "04c996bcec75"
down_revision: Union[str, Sequence[str], None] = "9e5b71542701"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("sessions_invalidated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user", "sessions_invalidated_at")
