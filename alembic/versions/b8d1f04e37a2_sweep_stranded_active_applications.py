"""sweep stranded active applications on closed jobs

Revision ID: b8d1f04e37a2
Revises: a4c7e91b2d63
Create Date: 2026-07-22 00:00:00.000000

Remediation for applications left in an active status on a job that is already
CLOSED. Two code paths produced them, both fixed in the same release: a close
that entered CLOSED from a status other than PUBLISHED skipped the cascade, and
``push_match`` created applications without checking the job's status.

Fixing the producers does not repair the rows already in that state, and
nothing else ever will — the close cascade only fires on the transition, and
re-closing an already-CLOSED job is a no-op. Left alone they would sit active
forever, and because the purge now (correctly) preserves any candidate with an
active application, those candidates would be exempt from the 12-month
retention policy indefinitely. That is the reason this runs as a data
migration rather than being left for someone to notice.

Each swept row gets an audit entry with a NULL actor, matching how the nightly
purge records system-initiated changes. The affected candidates are not
emailed: the closures happened months ago, the applications are historical,
and a batch of "the job you applied to has closed" mails about long-dead
postings would be worse than silence.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b8d1f04e37a2"
down_revision: Union[str, Sequence[str], None] = "a4c7e91b2d63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mirrors ``ACTIVE_APPLICATION_STATUSES`` in rs_shared/enums.py, spelled out as
# literals on purpose. A migration must keep applying the definition that was
# true when it was written even if the enum's active group changes later, and
# inline literals keep the statements renderable under `alembic upgrade --sql`,
# which is the review step this repo mandates (.claude/rules/migrations.md).
_STRANDED = """
    FROM application a
    JOIN job j ON j.id = a.job_id
    WHERE j.status = 'CLOSED'
      AND a.status IN (
          'PENDING_ADMIN_REVIEW', 'APPROVED_BY_ADMIN', 'INTERVIEWING', 'OFFER'
      )
"""


def upgrade() -> None:
    """Upgrade schema."""
    # Audit first — once the UPDATE lands, the rows no longer match the filter.
    op.execute(
        f"""
        INSERT INTO audit_log (
            actor_user_id, action, target_type, target_id, detail, created_at
        )
        SELECT
            NULL,
            'application.status_change',
            'Application',
            a.id,
            'JOB_CLOSED (backfill: stranded active on closed job '
                || a.job_id || ')',
            now()
        {_STRANDED}
        """
    )

    op.execute(
        f"""
        UPDATE application
        SET status = 'JOB_CLOSED', updated_at = now()
        WHERE id IN (SELECT a.id {_STRANDED})
        """
    )


def downgrade() -> None:
    """Downgrade schema.

    Not reversible: the pre-sweep status of each application is not recorded
    anywhere, so there is nothing to restore it from. The audit rows written by
    ``upgrade`` are the only trace, and they are append-only by design.
    """
    pass
