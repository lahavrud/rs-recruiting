"""drop job_match table

Revision ID: 5237dfa3ad52
Revises: db10eb69ce40
Create Date: 2026-06-24 12:00:50.776568

Resume matching dropped persisted top-N matches in favor of computing both
directions (candidate->jobs and job->candidates) live with a cosine-distance
query at read time — one query shape, no staleness to reconcile when a job
publishes/closes or a candidate's resume changes. See
``src.services.admin.candidates.get_candidate_job_matches`` and
``src.services.admin.jobs.get_job_candidate_matches``.

The ``job.embedding`` / ``candidateprofile.embedding`` columns and the
``vector`` extension added by ``db10eb69ce40`` are untouched — only the
``job_match`` table goes away.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5237dfa3ad52"
down_revision: Union[str, Sequence[str], None] = "db10eb69ce40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index("uq_job_match_candidate_job", table_name="job_match")
    op.drop_index(op.f("ix_job_match_job_id"), table_name="job_match")
    op.drop_index(op.f("ix_job_match_candidate_id"), table_name="job_match")
    op.drop_table("job_match")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "job_match",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidateprofile.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_match_candidate_id"), "job_match", ["candidate_id"])
    op.create_index(op.f("ix_job_match_job_id"), "job_match", ["job_id"])
    op.create_index(
        "uq_job_match_candidate_job",
        "job_match",
        ["candidate_id", "job_id"],
        unique=True,
    )
