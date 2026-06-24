"""Candidate profile and application schemas."""

import os
import re
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.enums import ApplicationStatus
from src.schemas.jobs import JobRead


def _validate_phone_value(v: str | None) -> str | None:
    """Validate phone number format — Israeli mobile only.

    Accepts any input shape that, after stripping spaces / `+` / `-` / `(` / `)`,
    is exactly 10 digits starting with `05` (e.g. `0501234567`, `050-123-4567`,
    `+972 50 123 4567` does NOT pass — candidates must use the local form).
    """
    if v is None or v == "":
        return None
    pattern = r"^[+\d\s()-]*$"
    if not re.match(pattern, v):
        raise ValueError("Phone number may only contain digits, spaces, +, -, (, )")
    digits = re.sub(r"\D", "", v)
    if not re.fullmatch(r"05\d{8}", digits):
        raise ValueError("Phone must be a valid Israeli mobile number (05X-XXXXXXX)")
    return v


def _validate_linkedin_url_value(v: str | None) -> str | None:
    """Validate LinkedIn URL format."""
    if v is None or v == "":
        return None
    parsed = urlparse(v)
    if parsed.scheme != "https":
        raise ValueError("LinkedIn URL must start with https://")
    hostname = parsed.hostname or ""
    if not (hostname == "linkedin.com" or hostname.endswith(".linkedin.com")):
        raise ValueError("LinkedIn URL must be a linkedin.com address")
    return v


class CandidateProfileCreate(BaseModel):
    """Schema for creating a candidate profile (application form)."""

    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr = Field(..., max_length=255)
    phone: str = Field(..., max_length=30)
    resume_path: str | None = None
    linkedin_url: str | None = Field(None, max_length=500)

    @field_validator("resume_path")
    @classmethod
    def validate_resume_path(cls, v: str | None) -> str | None:
        """Validate resume path to prevent path traversal attacks.

        Note: This field is typically not set manually. The service layer
        handles file uploads and sets resume_path automatically with UUID-based
        identifiers from the storage provider.

        Security Rules:
        - Reject paths containing path traversal sequences ('../', '..\\')
        - Reject absolute paths (starting with '/' or '\\')
        - Allow None values (optional field)

        Args:
            v: The resume path to validate

        Returns:
            The validated path or None

        Raises:
            ValueError: If path contains malicious patterns
        """
        if v is None:
            return None

        # Reject paths with parent directory traversal sequences
        if "../" in v or "..\\" in v:
            raise ValueError(
                "Path cannot contain path traversal sequences ('../' or '..\\')"
            )

        # Reject absolute paths
        if v.startswith("/") or v.startswith("\\"):
            raise ValueError(
                "Path cannot be absolute (must not start with '/' or '\\')"
            )

        # Normalize the path to resolve any redundant separators
        normalized = os.path.normpath(v)

        # Additional check: ensure no path traversal after normalization
        if ".." in normalized:
            raise ValueError("Path cannot contain '..' (parent directory reference)")

        return normalized

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number format."""
        if not v.strip():
            raise ValueError("Phone number is required")
        result = _validate_phone_value(v)
        if result is None:
            raise ValueError("Phone number is required")
        return result

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, v: str | None) -> str | None:
        """Validate LinkedIn URL format."""
        return _validate_linkedin_url_value(v)


class CandidateProfileRead(BaseModel):
    """Schema for reading candidate profile data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    phone: str | None
    resume_path: str | None
    linkedin_url: str | None
    consent_given_at: datetime | None
    consent_policy_version: str | None
    tos_accepted_at: datetime | None
    tos_version: str | None
    created_at: datetime


class CandidateMeRead(BaseModel):
    """Self-service candidate profile read.

    Returned by ``GET /api/candidate/me``. Pulls ``email`` from the linked
    ``User`` (since the auth identity is the source of truth) and exposes
    the editable identity fields + the consent record. Excludes admin-only
    fields like ``deleted_at`` and per-application ``resume_path`` snapshots
    (those live on ``Application``).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str | None
    linkedin_url: str | None
    resume_path: str | None
    resume_filename: str | None
    consent_given_at: datetime | None
    consent_policy_version: str | None
    created_at: datetime


class CandidateMeUpdate(BaseModel):
    """Self-service candidate profile update.

    Editable fields only: ``full_name``, ``phone``, ``linkedin_url``,
    ``resume_filename`` (basename only — see validator).

    ``email`` is intentionally absent — auth identity is set at registration
    and a candidate-side email change requires re-verification, which is
    out of scope for MVP. The router rejects requests that include ``email``
    in the body (rather than silently dropping it).
    """

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(None, min_length=2, max_length=100)
    phone: str | None = Field(None, max_length=30)
    linkedin_url: str | None = Field(None, max_length=500)
    # 100-char cap covers any reasonable resume filename and keeps the
    # candidate-facing UI readable. Tighter than the DB column's
    # max_length=255 — the column bounds storage, this bounds policy.
    resume_filename: str | None = Field(None, max_length=100)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """Phone is nullable on the model — explicit-null on PATCH clears it.

        Only ``full_name`` + ``email`` are mandatory identity on the profile;
        ``phone`` (along with ``linkedin_url`` and ``resume_path``) is
        autofill metadata for the apply form. The app-level invariant that
        an Application requires a phone is enforced at the apply-form
        endpoint, not here.
        """
        if v is None:
            return None
        return _validate_phone_value(v)

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, v: str | None) -> str | None:
        return _validate_linkedin_url_value(v)

    @field_validator("resume_filename")
    @classmethod
    def validate_resume_filename(cls, v: str | None) -> str | None:
        """Shape-validate the resume filename label.

        The extension lock (must match the stored file's) is enforced at
        the service layer because the schema can't see profile state.
        Here we just reject path-traversal / unsafe characters so the
        label can't be used to smuggle anything weird into the storage
        key (which lives on a separate column anyway).
        """
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("resume_filename cannot be blank")
        # Reject path separators + traversal — defence in depth even
        # though the storage key is a separate column.
        if "/" in stripped or "\\" in stripped or ".." in stripped:
            raise ValueError("resume_filename cannot contain path separators")
        # Allow letters/digits/space/dot/hyphen/underscore/parentheses
        # plus a small set of locale punctuation. Reject control bytes
        # and obvious shell metas.
        if any(c in stripped for c in '<>:"|?*\x00'):
            raise ValueError("resume_filename contains unsafe characters")
        return stripped


class ApplicationCreate(BaseModel):
    """Schema for creating an application (match)."""

    job_id: int
    candidate_id: int


class ApplicationStatusUpdate(BaseModel):
    """Schema for admin status updates on an application.

    status is required — use ApplicationUpdate for partial updates
    where status is optional.
    """

    status: ApplicationStatus
    admin_notes: str | None = Field(None, max_length=2000)


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""

    status: ApplicationStatus | None = None
    admin_notes: str | None = Field(None, max_length=2000)


class ApplicationNotesUpdate(BaseModel):
    """Schema for updating only the admin_notes field on an application."""

    admin_notes: str | None = Field(None, max_length=2000)


class ApplicationRead(BaseModel):
    """Schema for reading application data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    candidate_id: int
    status: ApplicationStatus
    admin_notes: str | None
    service_concept: str | None
    salary_expectations: str | None
    strength: str | None
    growth_area: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationWithDetails(BaseModel):
    """Schema for application with related job and candidate details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    candidate_id: int
    status: ApplicationStatus
    admin_notes: str | None
    service_concept: str | None
    salary_expectations: str | None
    strength: str | None
    growth_area: str | None
    created_at: datetime
    updated_at: datetime
    job: JobRead
    candidate: CandidateProfileRead


# --------------------------------------------------------------------------
# Candidate-facing application views
#
# Deliberately omit raw ``status`` and ``admin_notes`` — the candidate sees
# only the derived ``editable`` boolean. WITHDRAWN rows are filtered upstream
# in the service layer, so the field doesn't need to appear here either.
# --------------------------------------------------------------------------


class CandidateApplicationJobSummary(BaseModel):
    """Minimal job snapshot embedded in the candidate's application list rows."""

    id: int
    title: str
    closed: bool


class CandidateApplicationJobDetail(BaseModel):
    """Job snapshot embedded in the application detail view — adds description."""

    id: int
    title: str
    description: str
    closed: bool


class CandidateApplicationCompany(BaseModel):
    """Company snapshot embedded in candidate-facing application responses."""

    id: int
    name: str


class CandidateApplicationListItem(BaseModel):
    """Row shape for ``GET /api/candidate/me/applications``."""

    id: int
    submitted_at: datetime
    editable: bool
    job: CandidateApplicationJobSummary
    company: CandidateApplicationCompany


class CandidateApplicationMyAnswers(BaseModel):
    """The candidate's own answers — what they submitted, not what admin saw."""

    service_concept: str | None
    salary_expectations: str | None
    strength: str | None
    growth_area: str | None


class CandidateJobMatchRead(BaseModel):
    """One ranked job match for the admin candidate view.

    Computed live (cosine distance) against every PUBLISHED, embedded job —
    see ``JobCandidateMatchRead`` for the reverse direction. ``score`` is
    cosine similarity in [0, 1] (higher = better match).
    """

    model_config = ConfigDict(from_attributes=True)

    job: JobRead
    score: float


class JobCandidateMatchRead(BaseModel):
    """One ranked candidate match for the admin job view.

    Computed live (cosine distance) against every embedded candidate — see
    ``CandidateJobMatchRead`` for the reverse direction. ``score`` is cosine
    similarity in [0, 1].
    """

    model_config = ConfigDict(from_attributes=True)

    candidate: CandidateProfileRead
    score: float


class CandidateApplicationResumeMeta(BaseModel):
    """Resume snapshot metadata — only filename + a present/absent flag."""

    filename: str
    snapshot_present: bool


class CandidateApplicationDetail(BaseModel):
    """Response for ``GET /api/candidate/me/applications/:id``."""

    id: int
    submitted_at: datetime
    editable: bool
    job: CandidateApplicationJobDetail
    company: CandidateApplicationCompany
    my_answers: CandidateApplicationMyAnswers
    resume: CandidateApplicationResumeMeta | None
