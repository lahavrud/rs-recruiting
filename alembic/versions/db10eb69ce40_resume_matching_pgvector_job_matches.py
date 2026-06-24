"""resume matching: pgvector + job matches

Revision ID: db10eb69ce40
Revises: 6e26d8b21e9c
Create Date: 2026-06-24 09:49:18.253131

Adds the resume-matching engine schema:
- the pgvector ``vector`` extension
- ``embedding`` columns on ``job`` and ``candidateprofile``
- ``candidateprofile.parsed_text`` (extracted CV text)
- the ``job_match`` table (persisted top-N matches per candidate)

The embedding width (1024) MUST match ``settings.embedding_dim`` and the model's
output dimension. Changing the model's dimension later needs a new migration.

NB: requires the ``vector`` extension to be available in the target Postgres
(local: use the ``pgvector/pgvector`` image; RDS: enable in the parameter group).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "db10eb69ce40"
down_revision: Union[str, Sequence[str], None] = "6e26d8b21e9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EMBEDDING_DIM = 1024


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "job",
        sa.Column("embedding", Vector(_EMBEDDING_DIM), nullable=True),
    )
    op.add_column(
        "candidateprofile",
        sa.Column("parsed_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "candidateprofile",
        sa.Column("embedding", Vector(_EMBEDDING_DIM), nullable=True),
    )

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


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_job_match_candidate_job", table_name="job_match")
    op.drop_index(op.f("ix_job_match_job_id"), table_name="job_match")
    op.drop_index(op.f("ix_job_match_candidate_id"), table_name="job_match")
    op.drop_table("job_match")
    op.drop_column("candidateprofile", "embedding")
    op.drop_column("candidateprofile", "parsed_text")
    op.drop_column("job", "embedding")
    # Leave the ``vector`` extension installed — other objects may rely on it
    # and dropping an extension is rarely what a downgrade wants.
