"""split_and_extend_application_status

Revision ID: bb83663b843e
Revises: 04c996bcec75
Create Date: 2026-07-10 21:00:00.000000

Reshapes the ``applicationstatus`` Postgres enum:

- renames ``NEW`` to ``PENDING_ADMIN_REVIEW`` (parallels
  ``JobStatus.PENDING_APPROVAL`` and names the awaited actor);
- adds the ``INTERVIEWING`` and ``OFFER`` company-pipeline stages;
- splits the overloaded ``REJECTED`` value by actor into
  ``REJECTED_BY_ADMIN`` (RS screen-out, before the employer sees the
  candidate) and ``REJECTED_BY_COMPANY`` (employer decline after review).

Backfill of existing rows:

- every ``NEW`` row becomes ``PENDING_ADMIN_REVIEW``;
- every existing ``REJECTED`` row becomes ``REJECTED_BY_ADMIN``. Historically
  the value was overwhelmingly an RS-side screen-out and the actor was never
  recorded, so all legacy rejections are attributed to admin;
  ``REJECTED_BY_COMPANY`` only accrues going forward, from employer decisions.

Done as a single type-recreation so the old ``NEW`` and ``REJECTED`` labels are
dropped cleanly (Postgres cannot rename/remove an enum value in place without
recreating the type). ``application.status`` is the only column using the type.
The ``ix_application_status`` index is rebuilt automatically by
``ALTER COLUMN ... TYPE``.

SQLite (test path): the column is plain TEXT — no DDL needed, and the schema
is built from SQLModel metadata via ``create_all``.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "bb83663b843e"
down_revision: Union[str, Sequence[str], None] = "04c996bcec75"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENUM_NAME = "applicationstatus"

# Pipeline order — mirror of rs_shared.enums.ApplicationStatus._STATUS_SORT_ORDER.
_NEW_VALUES = (
    "PENDING_ADMIN_REVIEW",
    "APPROVED_BY_ADMIN",
    "INTERVIEWING",
    "OFFER",
    "HIRED",
    "REJECTED_BY_COMPANY",
    "REJECTED_BY_ADMIN",
    "WITHDRAWN",
    "JOB_CLOSED",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    labels = ", ".join(f"'{v}'" for v in _NEW_VALUES)
    op.execute(f"ALTER TYPE {_ENUM_NAME} RENAME TO {_ENUM_NAME}_old")
    op.execute(f"CREATE TYPE {_ENUM_NAME} AS ENUM ({labels})")
    # The partial-unique index predicate references the enum type, so it must be
    # dropped before the column can be retyped and recreated afterwards — a plain
    # ALTER COLUMN TYPE would fail with an operator mismatch against the old type.
    op.execute("DROP INDEX IF EXISTS uq_application_job_candidate_active")
    op.execute(
        f"ALTER TABLE application ALTER COLUMN status TYPE {_ENUM_NAME} USING ("
        "  CASE"
        "    WHEN status::text = 'NEW' THEN 'PENDING_ADMIN_REVIEW'"
        "    WHEN status::text = 'REJECTED' THEN 'REJECTED_BY_ADMIN'"
        "    ELSE status::text"
        f"  END::{_ENUM_NAME})"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_application_job_candidate_active "
        "ON application (job_id, candidate_id) "
        "WHERE status != 'WITHDRAWN'"
    )
    op.execute(f"DROP TYPE {_ENUM_NAME}_old")


def downgrade() -> None:
    # Collapsing REJECTED_BY_* back to a single REJECTED and dropping the new
    # pipeline stages is lossy; migrate data off the new values first if a
    # rollback is ever required. Best-effort no-op mirrors 9fb910c7eb8d.
    pass
