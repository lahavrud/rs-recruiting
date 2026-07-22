"""Job posting model."""

from __future__ import annotations

from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, event, inspect
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


@event.listens_for(Session, "before_flush")
def _stamp_job_closed_at(
    session: Session, flush_context: object, instances: object
) -> None:
    """Keep ``Job.closed_at`` in lockstep with the CLOSED status.

    The retention purge treats ``closed_at`` as the start of the window, and a
    CLOSED job with a NULL anchor is preserved forever — so a close path that
    forgets to stamp it fails silently, as over-retention with no error and a
    plausible-looking nightly purge count.

    Enforcing it here rather than at each call site means it cannot be
    forgotten: it covers ``update_job``, ``reject_job``, ``admin_create_job``,
    the seed script, and any future path, including a raw ``job.status =
    CLOSED`` in a shell. Listening on ``Session`` catches ``AsyncSession`` too,
    which delegates to a sync session underneath.

    An explicit ``closed_at`` assignment still wins when the status is not
    changing in the same flush — that is what lets tests backdate the anchor.
    """
    now = datetime.now(timezone.utc)

    for obj in session.new:
        if isinstance(obj, Job) and obj.status == JobStatus.CLOSED:
            if obj.closed_at is None:
                obj.closed_at = now

    for obj in session.dirty:
        if not isinstance(obj, Job):
            continue
        # session.dirty is a superset of actually-modified objects, and an
        # unrelated edit to a closed job must not move the anchor.
        if not inspect(obj).attrs.status.history.has_changes():
            continue
        if obj.status == JobStatus.CLOSED:
            obj.closed_at = now
        elif obj.closed_at is not None:
            obj.closed_at = None
