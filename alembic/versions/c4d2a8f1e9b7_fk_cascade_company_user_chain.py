"""FK ON DELETE CASCADE on user / company / job chain

Revision ID: c4d2a8f1e9b7
Revises: d84645c6404c
Create Date: 2026-05-12 10:00:00.000000

Before this change, deleting a User that had a PasswordResetToken (added in
e7f3a2b1c8d4) raised a FK violation because the service-layer cascade in
admin_companies.delete_active_company hadn't been updated to clear the new
table. Rather than chase every new FK manually, this migration promotes the
seven user/company/job-chain FKs to ON DELETE CASCADE so the database does
the cascade. The matching service code is simplified in the same change.

Tables / columns altered (all on PostgreSQL only; SQLite test paths use
metadata.create_all from src/models.py which carries the same ondelete):

    activationtoken.company_user_id      -> user.id       CASCADE
    refreshtoken.user_id                 -> user.id       CASCADE
    passwordresettoken.user_id           -> user.id       CASCADE
    companyprofile.user_id (nullable)    -> user.id       CASCADE
    job.company_id                       -> companyprofile.id   CASCADE
    application.job_id                   -> job.id        CASCADE
    application.candidate_id             -> candidateprofile.id CASCADE

invitetoken.created_by_admin_id is intentionally left RESTRICT — admins
must not be silently deletable via the cascade.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c4d2a8f1e9b7"
down_revision: Union[str, Sequence[str], None] = "d84645c6404c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column, ref_table, ref_column, constraint_name)
_FK_CHANGES = [
    (
        "activationtoken",
        "company_user_id",
        "user",
        "id",
        "activationtoken_company_user_id_fkey",
    ),
    ("refreshtoken", "user_id", "user", "id", "refreshtoken_user_id_fkey"),
    ("passwordresettoken", "user_id", "user", "id", "passwordresettoken_user_id_fkey"),
    ("companyprofile", "user_id", "user", "id", "companyprofile_user_id_fkey"),
    ("job", "company_id", "companyprofile", "id", "job_company_id_fkey"),
    ("application", "job_id", "job", "id", "application_job_id_fkey"),
    (
        "application",
        "candidate_id",
        "candidateprofile",
        "id",
        "application_candidate_id_fkey",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # The test suite drives schema via SQLModel.metadata.create_all; the
        # ondelete clauses in src/models.py keep the test DB in lockstep.
        # Non-postgres production isn't supported, so there's nothing to do.
        return
    for table, column, ref_table, ref_column, name in _FK_CHANGES:
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{name}"')
        op.create_foreign_key(
            name,
            table,
            ref_table,
            [column],
            [ref_column],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table, column, ref_table, ref_column, name in _FK_CHANGES:
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{name}"')
        op.create_foreign_key(
            name,
            table,
            ref_table,
            [column],
            [ref_column],
        )
