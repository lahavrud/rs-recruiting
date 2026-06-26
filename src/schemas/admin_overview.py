"""Admin overview response schema."""

from pydantic import BaseModel


class TopJobEntry(BaseModel):
    id: int
    title: str
    application_count: int


class RecentItem(BaseModel):
    type: str  # "company" | "job" | "application"
    label: str
    sublabel: str | None
    created_at: str  # ISO 8601


class AdminInboxCounts(BaseModel):
    pending_invites: int
    pending_companies: int
    pending_jobs: int
    new_applications: int
    oldest_pending_company_days: int | None
    oldest_pending_job_days: int | None
    oldest_new_application_days: int | None


class AdminStatsCounts(BaseModel):
    active_companies: int
    published_jobs: int
    total_candidates: int
    application_status_counts: dict[str, int]
    top_jobs: list[TopJobEntry]


class TrendPoint(BaseModel):
    date: str  # ISO 8601 date (YYYY-MM-DD)
    n: int


class AdminPulse(BaseModel):
    new_candidates_7d: int
    new_applications_7d: int
    recent_items: list[RecentItem]
    trend_30d: list[TrendPoint]


class AdminOverviewRead(BaseModel):
    inbox: AdminInboxCounts
    stats: AdminStatsCounts
    pulse: AdminPulse
