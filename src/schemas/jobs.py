"""Job posting schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.enums import JobStatus

JOB_SHORT_DESC_MAX = 140
JOB_TAG_MAX_LEN = 30
JOB_TAG_MAX_COUNT = 6
JOB_REQ_TEXT_MAX = 200
JOB_REQ_MIN_COUNT = 3
JOB_REQ_MAX_COUNT = 15


class JobRequirementItem(BaseModel):
    """A single requirement bullet."""

    text: str = Field(..., min_length=1, max_length=JOB_REQ_TEXT_MAX)

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("requirement text cannot be empty")
        return stripped


def _validate_requirements(
    v: list[JobRequirementItem],
) -> list[JobRequirementItem]:
    if not (JOB_REQ_MIN_COUNT <= len(v) <= JOB_REQ_MAX_COUNT):
        raise ValueError(
            f"requirements must have between {JOB_REQ_MIN_COUNT} and "
            f"{JOB_REQ_MAX_COUNT} items"
        )
    return v


def _validate_tags(v: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in v:
        tag = raw.strip()
        if not tag:
            continue
        if len(tag) > JOB_TAG_MAX_LEN:
            raise ValueError(f"tag must be at most {JOB_TAG_MAX_LEN} characters")
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(tag)
    if len(cleaned) > JOB_TAG_MAX_COUNT:
        raise ValueError(f"at most {JOB_TAG_MAX_COUNT} tags allowed")
    return cleaned


class JobCreate(BaseModel):
    """Schema for creating a job posting."""

    title: str = Field(..., max_length=100)
    short_description: str = Field(..., min_length=1, max_length=JOB_SHORT_DESC_MAX)
    description: str = Field(..., max_length=5000)
    requirements: list[JobRequirementItem]
    tags: list[str] = Field(default_factory=list)
    location: str = Field(..., max_length=100)
    salary_min: int = Field(..., ge=0)
    salary_max: int = Field(..., ge=0)

    _validate_requirements = field_validator("requirements")(_validate_requirements)
    _validate_tags = field_validator("tags")(_validate_tags)

    @model_validator(mode="after")
    def _check_salary_range(self):
        if self.salary_min > self.salary_max:
            raise ValueError("salary_min must be <= salary_max")
        return self


class JobUpdate(BaseModel):
    """Schema for a company updating their job posting.

    Fields backed by NOT NULL columns reject an explicit ``null`` so a PATCH
    cannot bypass the database constraint. ``is_featured`` is intentionally
    omitted — only admins toggle that flag (see ``JobAdminUpdate``).
    """

    title: str | None = Field(None, max_length=100)
    short_description: str | None = Field(
        None, min_length=1, max_length=JOB_SHORT_DESC_MAX
    )
    description: str | None = Field(None, max_length=5000)
    requirements: list[JobRequirementItem] | None = None
    tags: list[str] | None = None
    location: str | None = Field(None, max_length=100)
    salary_min: int | None = Field(None, ge=0)
    salary_max: int | None = Field(None, ge=0)
    status: JobStatus | None = None

    @field_validator(
        "title",
        "short_description",
        "description",
        "requirements",
        "tags",
        "location",
        "salary_min",
        "salary_max",
    )
    @classmethod
    def reject_explicit_null(cls, v: object) -> object:
        if v is None:
            raise ValueError("Field cannot be set to null on update")
        return v

    @field_validator("requirements")
    @classmethod
    def _validate_requirements_list(
        cls, v: list[JobRequirementItem]
    ) -> list[JobRequirementItem]:
        return _validate_requirements(v)

    @field_validator("tags")
    @classmethod
    def _validate_tags_list(cls, v: list[str]) -> list[str]:
        return _validate_tags(v)

    @model_validator(mode="after")
    def _check_salary_range(self):
        # Only enforce when BOTH bounds are being set in the same request;
        # partial updates that change only one bound rely on the DB CHECK
        # constraint ck_job_salary_range as the safety net.
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min must be <= salary_max")
        return self


class JobAdminCreate(BaseModel):
    """Schema for an admin creating a job posting against a specific company."""

    company_id: int
    title: str = Field(..., max_length=100)
    short_description: str = Field(..., min_length=1, max_length=JOB_SHORT_DESC_MAX)
    description: str = Field(..., max_length=5000)
    requirements: list[JobRequirementItem]
    tags: list[str] = Field(default_factory=list)
    is_featured: bool = False
    location: str = Field(..., max_length=100)
    salary_min: int = Field(..., ge=0)
    salary_max: int = Field(..., ge=0)
    status: JobStatus = JobStatus.PUBLISHED

    _validate_requirements = field_validator("requirements")(_validate_requirements)
    _validate_tags = field_validator("tags")(_validate_tags)

    @model_validator(mode="after")
    def _check_salary_range(self):
        if self.salary_min > self.salary_max:
            raise ValueError("salary_min must be <= salary_max")
        return self


class JobAdminUpdate(JobUpdate):
    """Admin-only update schema. Adds ``is_featured`` toggle."""

    is_featured: bool | None = None

    @field_validator("is_featured")
    @classmethod
    def _reject_null_featured(cls, v: bool | None) -> bool:
        if v is None:
            raise ValueError("Field cannot be set to null on update")
        return v


class JobRead(BaseModel):
    """Schema for reading job data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    company_name: str = ""
    title: str
    short_description: str
    description: str
    requirements: list[JobRequirementItem]
    tags: list[str]
    is_featured: bool
    location: str
    salary_min: int
    salary_max: int
    status: JobStatus
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="wrap")
    @classmethod
    def _populate_company_name(cls, value: Any, handler: Any) -> "JobRead":
        obj = handler(value)
        if not isinstance(value, dict):
            # Use vars() to read only already-loaded relationships — avoids
            # triggering async lazy loads in ORM paths that don't selectinload
            # the company (e.g. company-facing endpoints where the caller already
            # knows their own company name).
            loaded_company = vars(value).get("company")
            if loaded_company is not None:
                obj.company_name = loaded_company.name
        return obj


class MyApplicationInfo(BaseModel):
    """The candidate-facing slice of a candidate's own application.

    Returned on ``GET /api/public/jobs/:id`` when the request bears a valid
    candidate JWT. Withdrawn applications are filtered
    out server-side; ``editable`` is the only status-derived bit exposed to
    candidates.
    """

    id: int
    editable: bool


class JobPublicRead(BaseModel):
    """Schema for public job board responses.

    Excludes internal fields (company_id, status, updated_at) that should
    not be exposed to unauthenticated users. Status is omitted because the
    public endpoint only ever returns PUBLISHED jobs — it carries no
    information and leaks an internal enum.

    ``my_application`` is populated only for the per-job detail endpoint
    when the request bears a candidate JWT and that candidate has a
    non-withdrawn application for the job. Anonymous responses
    and list-endpoint responses leave it ``None``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    short_description: str
    description: str
    requirements: list[JobRequirementItem]
    tags: list[str]
    is_featured: bool
    location: str
    salary_min: int
    salary_max: int
    created_at: datetime
    my_application: MyApplicationInfo | None = None


class JobContactEmailRequest(BaseModel):
    """Schema for admin sending a contextual email to a company about a job."""

    admin_note: str = Field(default="", max_length=2000)
