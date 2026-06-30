"""merge account deletion into main migration chain

Revision ID: 29333542be15
Revises: 04c996bcec75, c5d6e7f8a9b0
Create Date: 2026-06-30 10:28:25.625856

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29333542be15'
down_revision: Union[str, Sequence[str], None] = ('04c996bcec75', 'c5d6e7f8a9b0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
