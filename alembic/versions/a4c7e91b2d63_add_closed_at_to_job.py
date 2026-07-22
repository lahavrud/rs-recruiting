"""add closed_at to job

Revision ID: a4c7e91b2d63
Revises: 29333542be15
Create Date: 2026-07-22 00:00:00.000000

Adds a nullable ``closed_at`` timestamp to ``job``, recording when the job
entered CLOSED. The candidate-retention purge previously measured the window
from ``updated_at``, which any later edit bumps — so editing a closed job
silently restarted the retention clock for every candidate who applied to it.

Existing CLOSED rows are backfilled from ``updated_at``. That reproduces
today's behaviour exactly at cutover, so no candidate becomes newly
purge-eligible the moment this lands. For jobs edited after they were closed
the backfilled value is late rather than accurate, meaning those rows
over-retain once — the safe direction — and stop drifting from here.

Expand-only: the column is nullable with no default and nothing reads it until
the accompanying code ships, so an ECS rollback to the previous image leaves a
harmless unused column.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a4c7e91b2d63"
down_revision: Union[str, Sequence[str], None] = "29333542be15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "job",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill closed jobs so the purge sees the same retention window it saw
    # before this migration. Guarded on NULL so a re-run is a no-op.
    op.execute(
        """
        UPDATE job
        SET closed_at = updated_at
        WHERE status = 'CLOSED'
          AND closed_at IS NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("job", "closed_at")
