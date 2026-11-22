"""add TOTP MFA tables (user_mfa, mfa_recovery_code, mfa_challenge)

Revision ID: a7c4e91b2d58
Revises: c3e9a7d51f20
Create Date: 2026-11-21 00:00:00.000000

Second-factor state for #1177: a per-user encrypted TOTP secret, single-use
hashed recovery codes, and the short-lived challenge rows that sit between the
password step and the code step of a login. Mirrors ``rs_shared.models.mfa``.

Also ``refreshtoken.mfa_verified``: whether a session passed the second
factor (a user with MFA on is refused any session without it).

Expand-only: three new tables and one column with a server default, so the
previous release keeps running unaffected during the rolling deploy (its new
sessions are written with ``mfa_verified = false``, which is right: nobody has
MFA on before this release).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a7c4e91b2d58"
down_revision: Union[str, None] = "c3e9a7d51f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_mfa",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_used_step", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "mfa_recovery_code",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_mfa_recovery_code_user_id", "mfa_recovery_code", ["user_id"])
    op.create_table(
        "mfa_challenge",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("remember_me", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_mfa_challenge_user_id", "mfa_challenge", ["user_id"])
    op.create_index("ix_mfa_challenge_expires_at", "mfa_challenge", ["expires_at"])
    op.add_column(
        "refreshtoken",
        sa.Column(
            "mfa_verified", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("refreshtoken", "mfa_verified")
    op.drop_index("ix_mfa_challenge_expires_at", table_name="mfa_challenge")
    op.drop_index("ix_mfa_challenge_user_id", table_name="mfa_challenge")
    op.drop_table("mfa_challenge")
    op.drop_index("ix_mfa_recovery_code_user_id", table_name="mfa_recovery_code")
    op.drop_table("mfa_recovery_code")
    op.drop_table("user_mfa")
