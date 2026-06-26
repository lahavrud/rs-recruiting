"""Admin overview response schema."""

from pydantic import BaseModel


class TopJobEntry(BaseModel):
    id: int
    title: str
    application_count: int


class AdminInboxCounts(BaseModel):
    pending_invites: int
    pending_companies: int
    pending_jobs: int
    new_applications: int


class AdminStatsCounts(BaseModel):
    active_companies: int
    published_jobs: int
    total_candidates: int
    application_status_counts: dict[str, int]
    top_jobs: list[TopJobEntry]


class AdminOverviewRead(BaseModel):
    inbox: AdminInboxCounts
    stats: AdminStatsCounts
