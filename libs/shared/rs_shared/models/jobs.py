"""Job posting model."""

from __future__ import annotations

from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DDL,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    event,
    inspect,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlmodel import Column, Field, Relationship, SQLModel

from rs_shared.enums import JobStatus
from rs_shared.models._embedding import EMBEDDING_DIM
from rs_shared.models.identity import CompanyProfile


class Job(SQLModel, table=True):
    """Job posting linked to a CompanyProfile.

    Jobs can be posted by companies and require admin approval before being published.
    """

    __table_args__ = (
        CheckConstraint(
            "salary_min <= salary_max",
            name="ck_job_salary_range",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("companyprofile.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    title: str
    short_description: str
    description: str
    requirements: list[dict] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    # Multilingual embedding of the job's text (title + descriptions +
    # requirements + tags + location), computed by ``embed_job_task`` on
    # publish/edit. NULL until first embedded. See core/services/embeddings.py.
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(EMBEDDING_DIM), nullable=True),
    )
    is_featured: bool = Field(default=False, index=True)
    location: str
    salary_min: int
    salary_max: int
    status: JobStatus = Field(default=JobStatus.PENDING_APPROVAL, index=True)
    # When the job entered CLOSED — the start of the candidate-retention window
    # (see services/admin/_candidates_purge.py). Distinct from ``updated_at``,
    # which any later edit bumps and which therefore cannot express "closed
    # since". NULL while the job has never been closed, and cleared again on
    # reopen so a stale value can't outlive the status.
    closed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=lambda: datetime.now(timezone.utc),
        ),
    )

    # Relationships
    company: CompanyProfile = Relationship()
    # Note: One-way relationship (SQLModel 0.0.22 limitation)
    # Access via: session.exec(select(Job).where(Job.company_id == X))


# ── closed_at invariant ───────────────────────────────────────────────────────
#
# ``closed_at`` anchors the candidate-retention window, and a CLOSED job with a
# NULL anchor is preserved forever — so a write that forgets to stamp it fails
# silently, as unbounded over-retention with no error and a plausible-looking
# nightly purge count. It is enforced in two places, deliberately:
#
#   * The database trigger below is the guarantee. It fires for every writer —
#     the ORM, ``session.execute(update(Job)...)``, a psql session, a future
#     service — because it is the only layer none of them can go around.
#   * The ``before_flush`` hook keeps the in-memory object agreeing with what
#     the trigger will do. Both session factories use ``expire_on_commit=False``
#     (see core/infrastructure/database.py), so without it ``job.closed_at``
#     would read stale after a close until someone called ``session.refresh``.
#
# They agree by construction: the hook stamps first, and the trigger only fills
# a NULL, so the ORM's value wins whenever both run.

_STAMP_CLOSED_AT_FN = DDL("""
CREATE OR REPLACE FUNCTION job_stamp_closed_at() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'CLOSED'
       AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'CLOSED') THEN
        -- Entering CLOSED. Only fill a NULL, so an explicitly supplied anchor
        -- (the ORM hook, or a backfill) is preserved rather than overwritten.
        IF NEW.closed_at IS NULL THEN
            NEW.closed_at := now();
        END IF;
    ELSIF NEW.status <> 'CLOSED' THEN
        -- Reopened: a stale anchor must not outlive the status.
        NEW.closed_at := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""")

# ``UPDATE OF status`` matters: it means an edit that does not touch the status
# never fires the trigger, so an unrelated change cannot move the anchor and a
# deliberate ``UPDATE job SET closed_at = ...`` (backfills, test fixtures aging
# a job) still lands. Re-closing an already-CLOSED row is likewise a no-op —
# OLD.status is not DISTINCT FROM 'CLOSED', so neither branch runs.
#
# One statement per DDL: asyncpg sends these as prepared statements and rejects
# multi-command strings. The migration drops first because it runs against an
# existing table; here the table has just been created, so there is nothing to
# drop.
_STAMP_CLOSED_AT_TRIGGER = DDL("""
CREATE TRIGGER job_closed_at_stamp
BEFORE INSERT OR UPDATE OF status ON job
FOR EACH ROW EXECUTE FUNCTION job_stamp_closed_at()
""")

# Attached to metadata so ``create_all`` installs it too. Dev, test and local
# compose build the schema that way rather than by running migrations
# (.claude/rules/migrations.md), so a trigger added only in the migration would
# be silently absent everywhere except production — the same trap that bit
# ``email_quota``.
event.listen(Job.__table__, "after_create", _STAMP_CLOSED_AT_FN)
event.listen(Job.__table__, "after_create", _STAMP_CLOSED_AT_TRIGGER)


@event.listens_for(Session, "before_flush")
def _stamp_job_closed_at(
    session: Session, flush_context: object, instances: object
) -> None:
    """Mirror the ``job_closed_at_stamp`` trigger onto in-memory Job objects.

    This is a convenience, not the guarantee — see the comment above. It exists
    because ``expire_on_commit=False`` means attributes are not reloaded after
    commit, so a caller reading ``job.closed_at`` straight after a close would
    otherwise see the pre-write value.

    Scoped to sessions that actually touch a Job: ``session.dirty`` is a
    computed property that walks the identity map, so the cheap ``session.new``
    scan runs first and the dirty scan is skipped entirely when no Job is
    loaded — which is most flushes in both services.
    """
    now = datetime.now(timezone.utc)

    for obj in session.new:
        if isinstance(obj, Job) and obj.status == JobStatus.CLOSED:
            if obj.closed_at is None:
                obj.closed_at = now

    if not any(isinstance(obj, Job) for obj in session.identity_map.values()):
        return

    for obj in session.dirty:
        if not isinstance(obj, Job):
            continue
        # An unrelated edit to a closed job must not move the anchor, and
        # SQLAlchemy reports no history when a value is re-set to itself, so a
        # re-close leaves the original anchor in place.
        if not inspect(obj).attrs.status.history.has_changes():
            continue
        if obj.status == JobStatus.CLOSED:
            obj.closed_at = now
        elif obj.closed_at is not None:
            obj.closed_at = None
