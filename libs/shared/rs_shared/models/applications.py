"""Application model — the core recruitment match linking a candidate to a job."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, text
from sqlmodel import Column, Field, Relationship, SQLModel

from rs_shared.enums import ApplicationStatus
from rs_shared.models.identity import CandidateProfile
from rs_shared.models.jobs import Job


class Application(SQLModel, table=True):
    """Application (Match) - the core business entity.

    Links a Candidate to a Job. Represents the recruitment match.

    `resume_path` snapshots the resume that was uploaded *for this specific
    application* at apply time. It is independent of
    `CandidateProfile.resume_path` (the latest resume on file). Allows
    candidates to swap their default resume without retroactively changing
    what companies already received.
    """

    # Partial unique index: a candidate cannot have two non-WITHDRAWN
    # applications for the same job, but WITHDRAWN ones don't block re-apply
    # — candidates can change their mind and apply again to a job they
    # previously withdrew from.
    __table_args__ = (
        Index(
            "uq_application_job_candidate_active",
            "job_id",
            "candidate_id",
            unique=True,
            postgresql_where=text("status != 'WITHDRAWN'"),
            sqlite_where=text("status != 'WITHDRAWN'"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("job.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    candidate_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("candidateprofile.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    status: ApplicationStatus = Field(
        default=ApplicationStatus.PENDING_ADMIN_REVIEW, index=True
    )
    admin_notes: str | None = Field(default=None, sa_column=Column(Text))
    service_concept: str | None = Field(default=None, sa_column=Column(Text))
    salary_expectations: str | None = Field(default=None, sa_column=Column(Text))
    strength: str | None = Field(default=None, sa_column=Column(Text))
    growth_area: str | None = Field(default=None, sa_column=Column(Text))
    resume_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    resume_filename: str | None = Field(default=None, max_length=255)
    resume_hash: str | None = Field(default=None, max_length=64)
    pushed_by_admin_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True
        ),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
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
    job: Job = Relationship()
    candidate: CandidateProfile = Relationship()
    # Note: One-way relationships (SQLModel 0.0.22 limitation)
    # Access job's applications via:
    # session.exec(select(Application).where(Application.job_id == job.id))
    # Access candidate's applications via:
    # session.exec(select(Application).where(Application.candidate_id == candidate.id))
