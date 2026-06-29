"""add_account_deletion_token_and_candidateprofile_deleted_at

Revision ID: a1b2c3d4e5f6
Revises: fb9f578fac9d
Create Date: 2026-06-29 00:00:00.000000

Schema changes for GDPR account deletion (#611):

- Adds ``candidateprofile.deleted_at`` — set by the deletion service when
  a right-to-erasure request is confirmed. PII fields are NULLed in the
  same transaction; the row is retained so Application history survives.
- Adds ``account_deletion_token`` table — single-use confirmation tokens
  for the two-step deletion flow. Keyed to ``candidateprofile.id`` (not
  ``user.id``) so the same token works for both authenticated candidates
  and anonymous leads.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "fb9f578fac9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # Tests build schema via SQLModel.metadata.create_all; this migration
        # is a no-op on non-Postgres backends.
        return

    # 1. candidateprofile.deleted_at — nullable timestamp, indexed for
    #    efficient "where deleted_at IS NULL" (exclude-tombstones) queries.
    op.add_column(
        "candidateprofile",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_candidateprofile_deleted_at", "candidateprofile", ["deleted_at"]
    )

    # 2. account_deletion_token table.
    op.create_table(
        "account_deletion_token",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("candidate_profile_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "used", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_profile_id"],
            ["candidateprofile.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_deletion_token_token_hash",
        "account_deletion_token",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_account_deletion_token_candidate_profile_id",
        "account_deletion_token",
        ["candidate_profile_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_index(
        "ix_account_deletion_token_candidate_profile_id",
        table_name="account_deletion_token",
    )
    op.drop_index(
        "ix_account_deletion_token_token_hash",
        table_name="account_deletion_token",
    )
    op.drop_table("account_deletion_token")

    op.drop_index("ix_candidateprofile_deleted_at", table_name="candidateprofile")
    op.drop_column("candidateprofile", "deleted_at")
