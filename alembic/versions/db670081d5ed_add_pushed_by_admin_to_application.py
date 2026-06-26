"""add_pushed_by_admin_to_application

Revision ID: db670081d5ed
Revises: b9b3da440b29
Create Date: 2026-06-27 01:02:26.137025

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "db670081d5ed"
down_revision: Union[str, Sequence[str], None] = "b9b3da440b29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "application", sa.Column("pushed_by_admin_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_application_pushed_by_admin_id",
        "application",
        "user",
        ["pushed_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_application_pushed_by_admin_id", "application", type_="foreignkey"
    )
    op.drop_column("application", "pushed_by_admin_id")
