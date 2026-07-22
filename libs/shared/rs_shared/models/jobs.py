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
    # ``onupdate`` is applied by SQLAlchemy when it builds the statement, not by
    # the database — so unlike ``closed_at``, this is *not* maintained for
    # writers that bypass the ORM. A hand-written `UPDATE job SET ...` in psql
    # leaves it stale.
    #
    # Deliberately not folded into the closed_at trigger. Doing so would mean
    # dropping that trigger's ``UPDATE OF status`` scoping to catch every write,
    # and it would then fire on data migrations' own statements — the closed_at
    # backfill does `UPDATE job SET closed_at = updated_at`, and bumping
    # updated_at underneath it is precisely the silent timestamp corruption this
    # column's history is a lesson in. Retention no longer depends on this
    # field; out-of-band writers that care about it should set it explicitly.
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
#   * The mapper-level hooks keep the in-memory object agreeing with what the
#     trigger will do. Both session factories use ``expire_on_commit=False``
#     (see core/infrastructure/database.py), so without them ``job.closed_at``
#     would read stale after a close until someone called ``session.refresh``.
#
# They agree branch for branch, and both only ever fill a NULL anchor, so a
# caller supplying its own ``closed_at`` while closing keeps it either way.
#
# These two strings are duplicated verbatim in the migration that installs them
# (alembic/versions/a4c7e91b2d63_*). That duplication is deliberate — a
# migration has to stay frozen, or replaying history would apply whatever the
# model says today rather than what the revision meant. It is also the obvious
# way for the two to drift, so ``tests/test_migrations.py`` compares them and
# fails if they diverge. If you change the trigger here, add a new migration:
# the test will tell you.
#
# Explanatory prose lives in Python comments rather than inside the SQL, so the
# two copies can be compared as-is instead of through a comment-stripping
# normaliser that could mask a real difference.
#
# Only fills a NULL on the way in, so an explicitly supplied anchor survives.
# Clears on the way out, so a stale anchor cannot outlive the CLOSED status.
CLOSED_AT_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION job_stamp_closed_at() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'CLOSED'
       AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'CLOSED') THEN
        IF NEW.closed_at IS NULL THEN
            NEW.closed_at := now();
        END IF;
    ELSIF NEW.status <> 'CLOSED' THEN
        NEW.closed_at := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# ``UPDATE OF status`` matters: it means an edit that does not touch the status
# never fires the trigger, so an unrelated change cannot move the anchor and a
# deliberate ``UPDATE job SET closed_at = ...`` (backfills, test fixtures aging
# a job) still lands. Re-closing an already-CLOSED row is likewise a no-op —
# OLD.status is not DISTINCT FROM 'CLOSED', so neither branch runs.
CLOSED_AT_TRIGGER_SQL = """
CREATE TRIGGER job_closed_at_stamp
BEFORE INSERT OR UPDATE OF status ON job
FOR EACH ROW EXECUTE FUNCTION job_stamp_closed_at()
"""

# One statement per DDL: asyncpg sends these as prepared statements and rejects
# multi-command strings. The migration drops the trigger first because it runs
# against an existing table; here it has just been created, so there is nothing
# to drop — which is why only these two strings are shared.
_STAMP_CLOSED_AT_FN = DDL(CLOSED_AT_FUNCTION_SQL)
_STAMP_CLOSED_AT_TRIGGER = DDL(CLOSED_AT_TRIGGER_SQL)

# Attached to metadata so ``create_all`` installs it too. Dev, test and local
# compose build the schema that way rather than by running migrations
# (.claude/rules/migrations.md), so a trigger added only in the migration would
# be silently absent everywhere except production — the same trap that bit
# ``email_quota``.
event.listen(Job.__table__, "after_create", _STAMP_CLOSED_AT_FN)
event.listen(Job.__table__, "after_create", _STAMP_CLOSED_AT_TRIGGER)


# The mirror. Both listeners are mapper-level rather than session-level, so
# SQLAlchemy dispatches them per Job actually being flushed — a request that
# loads a hundred rows and touches no job pays nothing, where a session-wide
# hook would walk the identity map on every flush in both services.
#
# Each mirrors one branch of the trigger exactly, including only ever filling a
# NULL anchor: a caller that supplies its own ``closed_at`` while closing (a
# data correction replaying a historical close) keeps it, rather than having the
# ORM overwrite what the trigger would have preserved. ``tests/models/
# test_job.py`` asserts the two layers agree on every branch.


@event.listens_for(Job, "before_insert")
def _stamp_closed_at_on_insert(mapper: object, connection: object, target: Job) -> None:
    """Mirror the trigger's INSERT branch onto the in-memory object."""
    if target.status == JobStatus.CLOSED and target.closed_at is None:
        target.closed_at = datetime.now(timezone.utc)


@event.listens_for(Job, "before_update")
def _stamp_closed_at_on_update(mapper: object, connection: object, target: Job) -> None:
    """Mirror the trigger's UPDATE branch onto the in-memory object."""
    # Matches the trigger's ``UPDATE OF status`` scoping: an edit that leaves
    # the status alone must not move the anchor. SQLAlchemy reports no history
    # when a value is re-set to itself, so a re-close is a no-op here just as
    # ``OLD.status IS DISTINCT FROM 'CLOSED'`` makes it one in the trigger.
    if not inspect(target).attrs.status.history.has_changes():
        return
    if target.status == JobStatus.CLOSED:
        if target.closed_at is None:
            target.closed_at = datetime.now(timezone.utc)
    elif target.closed_at is not None:
        target.closed_at = None
