"""add_match_suggestion

Revision ID: b9b3da440b29
Revises: 0d8005013ed8
Create Date: 2026-06-27 00:41:40.992040

Adds the MatchSuggestion table to track admin decisions on AI-generated match
suggestions (DISMISSED or PUSHED).  Absence of a row means the suggestion is
still active (implicitly pending).

Also removes the stale job_match table which was already dropped logically by
5237dfa3ad52 but survived in some environments due to a transactional edge-case.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9b3da440b29"
down_revision: str | Sequence[str] | None = "0d8005013ed8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # job_match was logically dropped by 5237dfa3ad52 but survived in some
    # environments — drop it if it still exists.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "job_match" in existing_tables:
        op.drop_index("uq_job_match_candidate_job", table_name="job_match")
        op.drop_index(op.f("ix_job_match_job_id"), table_name="job_match")
        op.drop_index(op.f("ix_job_match_candidate_id"), table_name="job_match")
        op.drop_table("job_match")

    if "matchsuggestion" not in existing_tables:
        op.create_table(
            "matchsuggestion",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("candidate_id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.Integer(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("acted_by_admin_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["acted_by_admin_id"],
                ["user.id"],
                name="matchsuggestion_acted_by_admin_id_fkey",
            ),
            sa.ForeignKeyConstraint(
                ["candidate_id"],
                ["candidateprofile.id"],
                name="matchsuggestion_candidate_id_fkey",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["job_id"],
                ["job.id"],
                name="matchsuggestion_job_id_fkey",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_matchsuggestion_candidate_id"),
            "matchsuggestion",
            ["candidate_id"],
        )
        op.create_index(
            op.f("ix_matchsuggestion_job_id"),
            "matchsuggestion",
            ["job_id"],
        )
        op.create_unique_constraint(
            "uq_match_suggestion",
            "matchsuggestion",
            ["candidate_id", "job_id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_match_suggestion", "matchsuggestion", type_="unique")
    op.drop_index(op.f("ix_matchsuggestion_job_id"), table_name="matchsuggestion")
    op.drop_index(op.f("ix_matchsuggestion_candidate_id"), table_name="matchsuggestion")
    op.drop_table("matchsuggestion")
