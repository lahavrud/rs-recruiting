"""resize embedding vectors from 1024 to 1536 dims for embed-v4.0

Revision ID: c9e3edf3bd29
Revises: 5237dfa3ad52
Create Date: 2026-06-25 20:38:39.291753

Upgrades the ``job.embedding`` and ``candidateprofile.embedding`` columns
from ``vector(1024)`` to ``vector(1536)`` to match the output dimension of
Cohere ``embed-v4.0`` (the replacement for ``embed-multilingual-v3.0``).

Existing 1024-dim vectors are incompatible with the new column type and are
nulled out. The backfill script (``scripts/backfill_embeddings.py``) must be
run after deploying the new code to re-embed all records.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e3edf3bd29"
down_revision: Union[str, Sequence[str], None] = "5237dfa3ad52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_DIM = 1024
_NEW_DIM = 1536


def upgrade() -> None:
    """Upgrade schema."""
    # Null existing 1024-dim vectors — they are incompatible with vector(1536)
    # and will be recomputed by the backfill script after deploy.
    op.execute("UPDATE job SET embedding = NULL")
    op.execute(
        f"ALTER TABLE job ALTER COLUMN embedding TYPE vector({_NEW_DIM}) "
        f"USING NULL::vector({_NEW_DIM})"
    )

    op.execute("UPDATE candidateprofile SET embedding = NULL")
    op.execute(
        f"ALTER TABLE candidateprofile ALTER COLUMN embedding TYPE vector({_NEW_DIM}) "
        f"USING NULL::vector({_NEW_DIM})"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE job SET embedding = NULL")
    op.execute(
        f"ALTER TABLE job ALTER COLUMN embedding TYPE vector({_OLD_DIM}) "
        f"USING NULL::vector({_OLD_DIM})"
    )

    op.execute("UPDATE candidateprofile SET embedding = NULL")
    op.execute(
        f"ALTER TABLE candidateprofile ALTER COLUMN embedding TYPE vector({_OLD_DIM}) "
        f"USING NULL::vector({_OLD_DIM})"
    )
