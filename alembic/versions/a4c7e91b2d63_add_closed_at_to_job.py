"""add closed_at to job

Revision ID: a4c7e91b2d63
Revises: c4a1e9b7d38f
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
down_revision: Union[str, Sequence[str], None] = "c4a1e9b7d38f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The anchor's guarantee. Every writer goes through the database, so this is the
# one layer a bulk UPDATE, a psql session or a future service cannot go around —
# the mapper-level hooks in models/jobs.py only keep in-memory objects in step
# with it.
#
# Copied verbatim from CLOSED_AT_FUNCTION_SQL / CLOSED_AT_TRIGGER_SQL in
# libs/shared/rs_shared/models/jobs.py, which is how dev and test get the same
# trigger (they build the schema with create_all, not by running migrations).
# Copied rather than imported because a migration must stay frozen: importing
# would make replaying history apply whatever the model says today.
# tests/test_migrations.py fails if the two ever diverge.
CLOSED_AT_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION job_stamp_closed_at() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'CLOSED'
       AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'CLOSED') THEN
        IF NEW.closed_at IS NULL THEN
            NEW.closed_at := now();
        END IF;
    ELSIF NEW.status <> 'CLOSED' THEN
        NEW.closed_at := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

CLOSED_AT_TRIGGER_SQL = """
CREATE TRIGGER job_closed_at_stamp
BEFORE INSERT OR UPDATE OF status ON job
FOR EACH ROW EXECUTE FUNCTION job_stamp_closed_at()
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "job",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill closed jobs so the purge sees the same retention window it saw
    # before this migration. Guarded on NULL so a re-run is a no-op.
    #
    # Deliberately one statement rather than a batched loop. Alembic wraps the
    # migration in a single transaction, so batching would not shorten how long
    # `job` is locked — and a rowcount-driven loop cannot run under
    # `alembic upgrade --sql`, which is the review step this repo mandates
    # (.claude/rules/migrations.md). The bound is therefore stated rather than
    # enforced: this touches one row per closed job, so confirm the scale is
    # what you expect before applying —
    #
    #     SELECT count(*) FROM job WHERE status = 'CLOSED';
    #
    # At the scale this app is built for that is a sub-second update. If it
    # ever returns millions, split this into an online batched backfill first.
    op.execute(
        """
        UPDATE job
        SET closed_at = updated_at
        WHERE status = 'CLOSED'
          AND closed_at IS NULL
        """
    )

    op.execute(CLOSED_AT_FUNCTION_SQL)
    # The table already exists here, unlike the create_all path, so an earlier
    # trigger of the same name could be present.
    op.execute("DROP TRIGGER IF EXISTS job_closed_at_stamp ON job")
    op.execute(CLOSED_AT_TRIGGER_SQL)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS job_closed_at_stamp ON job")
    op.execute("DROP FUNCTION IF EXISTS job_stamp_closed_at()")
    op.drop_column("job", "closed_at")
