"""Resume-matching model: admin decisions on AI-generated match suggestions."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlmodel import Column, Field, SQLModel

from rs_shared.enums import MatchSuggestionStatus


class MatchSuggestion(SQLModel, table=True):
    """Records admin decisions on AI-generated match suggestions.

    Absence of a row means the suggestion is still active (implicitly PENDING).
    Each (candidate, job) pair can only have one decision.
    """

    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_match_suggestion"),
    )

    id: int | None = Field(default=None, primary_key=True)
    candidate_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("candidateprofile.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    job_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("job.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    score: float = Field(sa_column=Column(Float, nullable=False))
    status: MatchSuggestionStatus
    acted_by_admin_id: int | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
