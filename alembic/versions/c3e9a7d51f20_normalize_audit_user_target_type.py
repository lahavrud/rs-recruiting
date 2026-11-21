"""normalize audit_log target_type 'user' to 'User'

Revision ID: c3e9a7d51f20
Revises: f8a12f04ae35
Create Date: 2026-11-21 00:00:00.000000

User rows were recorded under two target types: ``User`` (activation and
candidate registration) and ``user`` (password change/reset, admin login, admin
email change). ``list_audit_events`` filters by exact match, so a lookup by
either value returned only part of a user's history. The writers now all use
``User``, the PascalCase model-name form the other targets use; this rewrites
the rows already written.
"""

import logging
from typing import Sequence, Union

from alembic import op

_logger = logging.getLogger("alembic.runtime.migration")

revision: str = "c3e9a7d51f20"
down_revision: Union[str, Sequence[str], None] = "f8a12f04ae35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Module-level so tests/test_migrations.py runs this exact statement.
NORMALIZE_SQL = "UPDATE audit_log SET target_type = 'User' WHERE target_type = 'user'"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(NORMALIZE_SQL)


def downgrade() -> None:
    """Downgrade schema.

    No-op by design. Which rows were 'user' before the upgrade is not
    recorded, and the previous release reads both spellings the same way (no
    code filters on the lowercase value), so there is nothing to restore.
    """
    _logger.warning(
        "downgrade is a no-op: audit_log target_type stays 'User' (%s)", revision
    )
