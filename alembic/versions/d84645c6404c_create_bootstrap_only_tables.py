"""create the tables that were only ever built by create_all

Revision ID: d84645c6404c
Revises: b00a63289dff
Create Date: 2026-11-20 16:00:00.000000

``activationtoken``, ``refreshtoken`` and ``audit_log`` had SQLModel models but
no migration ever created them (#1058): prod got them from a one-time
``SQLModel.metadata.create_all``. Later migrations already ALTER them, so on an
empty database the chain failed at ``c4d2a8f1e9b7``, which recreates their
foreign keys.

This revision sits mid-chain, directly before ``c4d2a8f1e9b7`` (whose
``down_revision`` now points here), and creates each table in the shape it had
at that point. Later migrations then transform them exactly as they did on prod
(token -> token_hash, company_user_id -> user_id, dropped is_revoked, ...).
``audit_log`` has not changed since it was added.

On prod this never runs: it is an ancestor of the revision prod is already at,
so ``alembic upgrade head`` does not select it. Each table is still created
only when absent, so a database that already has it, in any shape (e.g. from
create_all), is left untouched.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d84645c6404c"
down_revision: Union[str, Sequence[str], None] = "b00a63289dff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Shapes as of mid-May 2026 (the models just before c4d2a8f1e9b7). Constraint
# and index names are the ones create_all produced and later migrations refer
# to: c4d2a8f1e9b7 drops "<table>_<column>_fkey", c57f61e2f435 drops
# ix_activationtoken_token, 8dbec9f8ada3 renames
# ix_activationtoken_company_user_id.
#
# Each table and its indexes are created together, and only when the table is
# absent. A per-statement IF NOT EXISTS is not enough: against today's shape
# (token_hash, user_id) the old index statements would fail on missing columns.


def _create_if_absent(table: str, statements: str) -> str:
    """One DO block (a single statement, as asyncpg needs) creating ``table``
    and its indexes when ``table`` does not exist yet."""
    return (
        "DO $$ BEGIN\n"
        f"IF to_regclass('{table}') IS NULL THEN\n"
        f"{statements.strip()}\n"
        "END IF;\n"
        "END $$"
    )


ACTIVATIONTOKEN_DDL = _create_if_absent(
    "activationtoken",
    """
    CREATE TABLE activationtoken (
        id SERIAL NOT NULL,
        token VARCHAR NOT NULL,
        company_user_id INTEGER NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        used BOOLEAN NOT NULL,
        CONSTRAINT activationtoken_pkey PRIMARY KEY (id),
        CONSTRAINT activationtoken_company_user_id_fkey
            FOREIGN KEY (company_user_id) REFERENCES "user" (id)
    );
    CREATE UNIQUE INDEX ix_activationtoken_token ON activationtoken (token);
    CREATE INDEX ix_activationtoken_company_user_id
        ON activationtoken (company_user_id);
    """,
)

REFRESHTOKEN_DDL = _create_if_absent(
    "refreshtoken",
    """
    CREATE TABLE refreshtoken (
        id SERIAL NOT NULL,
        token_hash VARCHAR NOT NULL,
        user_id INTEGER NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        is_revoked BOOLEAN NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        CONSTRAINT refreshtoken_pkey PRIMARY KEY (id),
        CONSTRAINT refreshtoken_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES "user" (id)
    );
    CREATE UNIQUE INDEX ix_refreshtoken_token_hash ON refreshtoken (token_hash);
    CREATE INDEX ix_refreshtoken_user_id ON refreshtoken (user_id);
    """,
)

# Append-only GDPR evidence; deliberately FK-free (see models/audit.py).
AUDIT_LOG_DDL = _create_if_absent(
    "audit_log",
    """
    CREATE TABLE audit_log (
        id SERIAL NOT NULL,
        actor_user_id INTEGER,
        action VARCHAR(64) NOT NULL,
        target_type VARCHAR(64) NOT NULL,
        target_id INTEGER NOT NULL,
        detail TEXT,
        ip_address VARCHAR(45),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        CONSTRAINT audit_log_pkey PRIMARY KEY (id)
    );
    CREATE INDEX ix_audit_log_actor_user_id ON audit_log (actor_user_id);
    CREATE INDEX ix_audit_log_action ON audit_log (action);
    CREATE INDEX ix_audit_log_target_type ON audit_log (target_type);
    CREATE INDEX ix_audit_log_target_id ON audit_log (target_id);
    CREATE INDEX ix_audit_log_created_at ON audit_log (created_at);
    """,
)

ALL_DDL = (ACTIVATIONTOKEN_DDL, REFRESHTOKEN_DDL, AUDIT_LOG_DDL)


def upgrade() -> None:
    for statement in ALL_DDL:
        op.execute(statement)


def downgrade() -> None:
    # Deliberately a no-op. On prod these tables pre-date the chain, and
    # dropping audit_log would destroy compliance evidence. upgrade() is
    # idempotent, so re-upgrading after a downgrade is safe.
    pass
