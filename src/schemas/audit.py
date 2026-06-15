"""Audit log schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    """Audit log entry returned by the admin query endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None
    action: str
    target_type: str
    target_id: int
    detail: str | None
    ip_address: str | None
    created_at: datetime


class CandidateActivityEvent(AuditLogRead):
    """Audit log entry enriched with job context for the candidate timeline.

    `job_title` is populated for `target_type="Application"` rows so the
    record pane can show which job an application event relates to.
    """

    job_title: str | None = None
