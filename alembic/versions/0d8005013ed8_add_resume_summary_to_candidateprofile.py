"""add resume_summary to candidateprofile

Revision ID: 0d8005013ed8
Revises: c9e3edf3bd29
Create Date: 2026-06-26 20:10:28.093616

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0d8005013ed8"
down_revision: Union[str, Sequence[str], None] = "c9e3edf3bd29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "candidateprofile", sa.Column("resume_summary", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("candidateprofile", "resume_summary")
