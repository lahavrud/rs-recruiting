from __future__ import annotations

import os
from datetime import datetime, timezone

from pydantic import field_validator
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel

from src.enums import ApplicationStatus, InviteTokenStatus, JobStatus, UserRole


class InviteToken(SQLModel, table=True):
    """Admin-issued invite tokens for gated company registration.

    Metadata is persisted here; Redis stores the live TTL/validity signal.
    """

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    email: str
    company_name: str | None = None
    contact_first_name: str | None = None
    contact_last_name: str | None = None
    note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: InviteTokenStatus = Field(default=InviteTokenStatus.PENDING)
    created_by_admin_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    used_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class ActivationToken(SQLModel, table=True):
    """One-time activation tokens for newly-registered users.

    Two flows mint these tokens:

    * COMPANY: admin approval — admin clicks "approve" on a pending company
      registration. The activation email goes to the company contact; the
      account flips to active when they click the link.
    * CANDIDATE: self-service registration — the candidate registers with
      email + password + consent. The activation email goes to the candidate;
      clicking the link creates / links their CandidateProfile and activates
      the account.

    `consent_policy_version` is set by the candidate flow at registration time
    so the policy version they agreed to is locked even if the policy changes
    before they click the link. NULL for company tokens (consent is captured
    on CompanyProfile at registration time, not at activation).
    """

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    used: bool = Field(default=False)
    consent_policy_version: str | None = Field(default=None, max_length=20)
    # Snapshotted at registration time for the candidate flow so the
    # CandidateProfile created at activation can prefill the name without
    # asking the user to type it again. NULL for company tokens (companies
    # carry their name on CompanyProfile, written at registration). Legacy
    # candidate tokens minted before this column existed are also NULL —
    # the activation service falls back to the email-prefix in that case.
    full_name: str | None = Field(default=None, max_length=100)


class RefreshToken(SQLModel, table=True):
    """Stored refresh tokens for the auth rotation flow.

    Tokens are stored as SHA-256 hashes. Each token is single-use:
    it is revoked and replaced on every refresh.
    """

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    remember_me: bool = Field(default=False)
    # Refresh tokens are deleted on use / logout / password change instead
    # of being marked revoked. A boolean revoked flag provided no security
    # benefit (revoked + missing were treated identically) and let dead
    # rows accumulate.
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class UsedRefreshToken(SQLModel, table=True):
    """Consumed refresh token hashes retained for replay detection.

    When a refresh token is rotated or invalidated on logout, its hash is
    written here with the same ``expires_at`` as the original token.  If the
    same hash is presented again before expiry, all active sessions for that
    user are nuked — a replay after rotation is a strong signal of token theft.
    Rows are cheap to keep until the original TTL elapses; expired rows are
    cleaned up passively at detection time, with bulk cleanup of expired
    rows left for a future scheduled job.
    """

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class DataExportRequest(SQLModel, table=True):
    """One-shot signed download token for the candidate GDPR data export.

    Candidates request an export → background task assembles a ZIP
    (profile JSON + per-application resumes) and uploads it to storage →
    row is minted here pointing at the ZIP's storage key → confirmation
    email contains a signed link `/api/candidate/me/export/{token}` →
    the GET endpoint streams the ZIP and marks `used=True`.

    Tokens are stored as SHA-256 hashes (raw token only ever lives in the
    email URL). `expires_at` is 24h from creation. Sweeping expired and
    used rows (and the corresponding storage objects) is left for a
    future scheduled job.
    """

    __tablename__ = "data_export_request"

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    download_path: str = Field(sa_column=Column(Text, nullable=False))
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    used: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class PasswordResetToken(SQLModel, table=True):
    """Single-use password-reset tokens.

    Stored as SHA-256 hashes; only the raw token (in the reset email link)
    can prove ownership. Marked `used=True` on successful reset.
    """

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    used: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class User(SQLModel, table=True):
    """Authenticated user entity (Admins, Companies, Candidates).

    Admins manage the platform. Companies post jobs. Candidates apply to jobs
    and manage their own applications. Anonymous applicants exist as bare
    CandidateProfile rows with no linked User — they're upgraded to a
    candidate User by registering or claiming via the public apply form.
    """

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    role: UserRole
    is_active: bool = Field(default=False, description="False until Admin approves")
    failed_login_attempts: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    locked_until: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # NOTE: annotation is the bare class for SQLModel 0.0.22 compatibility —
    # `Optional[CompanyProfile]` / `CompanyProfile | None` are rejected at
    # mapper init under `from __future__ import annotations`. The relationship
    # IS effectively nullable: ADMIN/CANDIDATE users have no company profile,
    # and after `selectinload(User.company_profile)` the value will be None.
    # See `tests/models/test_user.py::test_admin_user_company_profile_is_none`.
    company_profile: CompanyProfile = Relationship(
        back_populates="user",
        # `passive_deletes="all"` tells SQLAlchemy to leave FK rows alone and
        # rely on the DB's ON DELETE CASCADE (migration c4d2a8f1e9b7) — without
        # it, SA would issue `UPDATE companyprofile SET user_id=NULL` first and
        # orphan the profile instead of cascading.
        sa_relationship_kwargs={"uselist": False, "passive_deletes": "all"},
    )
    # 1:1 with CandidateProfile (effectively nullable: ADMIN/COMPANY users have
    # no candidate profile). FK uses ON DELETE SET NULL so that deleting a
    # candidate User leaves the profile as a tombstone for application history
    # (the deletion service then PII-scrubs the profile in place).
    # `passive_deletes="all"` keeps SQLAlchemy from issuing its own UPDATE
    # before the DELETE; we trust the DB-side SET NULL.
    candidate_profile: CandidateProfile = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"uselist": False, "passive_deletes": "all"},
    )


class CompanyProfile(SQLModel, table=True):
    """Company profile linked to a User.

    One-to-one relationship with User (for COMPANY role users).
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=True,
            unique=True,
            index=True,
        ),
    )
    name: str
    logo_url: str | None = None
    company_id: str  # ח.פ — 9-digit Israeli company registration number
    contact_email: str = Field(index=True, max_length=255)
    contact_first_name: str
    contact_last_name: str
    contact_mobile_phone: str
    contact_landline_phone: str | None = None
    address: str = Field(sa_column=Column(Text, nullable=False))
    agreement_signed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    agreement_signature_url: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    contract_pdf_url: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    privacy_accepted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    privacy_policy_version: str | None = Field(default=None, max_length=20)
    terms_accepted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    terms_version: str | None = Field(default=None, max_length=20)
    acceptance_ip: str | None = Field(default=None, max_length=45)
    acceptance_user_agent: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # NOTE: bare annotation for SQLModel 0.0.22 compatibility (see User above).
    # user_id is nullable (CompanyProfile may be created from an admin invite
    # before any User exists), so this relationship is effectively
    # `User | None` at runtime. See
    # `tests/models/test_user.py::test_orphan_company_profile_user_is_none`.
    user: User = Relationship(back_populates="company_profile")
    # Note: One-way relationships for Job and Application (SQLModel 0.0.22 limitation)
    # Access via queries: session.exec(select(Job).where(Job.company_id == company.id))


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
    is_featured: bool = Field(default=False, index=True)
    location: str
    salary_min: int
    salary_max: int
    status: JobStatus = Field(default=JobStatus.PENDING_APPROVAL, index=True)
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


class CandidateProfile(SQLModel, table=True):
    """Candidate profile.

    Either an anonymous lead (no `user_id`, created by the public apply form)
    OR a registered candidate (linked 1:1 with a `User(role=CANDIDATE)`).

    On `User` deletion the FK is SET NULL, leaving the profile in place so
    `Application` rows survive.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
            unique=True,
            index=True,
        ),
    )
    full_name: str
    email: str = Field(unique=True, index=True)
    # Optional — only full_name + email are mandatory for a candidate. Phone,
    # LinkedIn, and resume exist so per-application forms can autofill them
    # for a returning candidate, not as identity gates (Sprint 11 follow-up).
    phone: str | None = Field(default=None)
    resume_path: str | None = None
    # Display label for ``resume_path`` — set on upload from the user's
    # original ``UploadFile.filename`` and editable via PATCH (basename
    # only; the extension is locked to the stored file's). Nullable so
    # legacy rows (and PII-scrubbed deleted profiles) keep working with
    # the basename-of-storage-key UI fallback. Per-Application snapshots
    # of the filename are tracked separately.
    resume_filename: str | None = Field(default=None, max_length=255)
    resume_hash: str | None = Field(default=None, max_length=64)
    linkedin_url: str | None = None

    # Privacy consent — captured at application time
    consent_given_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    consent_policy_version: str | None = Field(default=None, max_length=20)
    consent_ip: str | None = Field(default=None, max_length=45)
    consent_user_agent: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    tos_accepted_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    tos_version: str | None = Field(default=None, max_length=20)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # 1:1 back-relationship to User. Effectively nullable at runtime: anonymous
    # leads have `user_id=None` and this resolves to None after
    # `selectinload(CandidateProfile.user)`. Bare-class annotation per the
    # SQLModel 0.0.22 limitation (see CompanyProfile.user above).
    user: User = Relationship(back_populates="candidate_profile")
    # Note: applications are one-way (SQLModel 0.0.22 limitation). Access via:
    # session.exec(select(Application).where(Application.candidate_id == candidate.id))

    @field_validator("resume_path")
    @classmethod
    def validate_resume_path(cls, v: str | None) -> str | None:
        """Validate resume path to prevent path traversal attacks.

        Security Rules:
        - Reject paths containing '..' (parent directory traversal)
        - Reject absolute paths (starting with '/')
        - Normalize path and ensure it stays within uploads/resumes/
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

        # Reject paths with parent directory traversal
        if ".." in v:
            raise ValueError("Path cannot contain '..' (parent directory reference)")

        # Reject absolute paths
        if v.startswith("/"):
            raise ValueError("Path cannot be absolute (must not start with '/')")

        # Normalize the path to resolve any redundant separators or references
        normalized = os.path.normpath(v)

        # Ensure normalized path doesn't escape the expected directory
        # All resume paths should be within uploads/resumes/
        if not normalized.startswith("uploads/resumes/"):
            raise ValueError("Path must be within 'uploads/resumes/' directory")

        return normalized


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
    status: ApplicationStatus = Field(default=ApplicationStatus.NEW, index=True)
    admin_notes: str | None = Field(default=None, sa_column=Column(Text))
    service_concept: str | None = Field(default=None, sa_column=Column(Text))
    salary_expectations: str | None = Field(default=None, sa_column=Column(Text))
    strength: str | None = Field(default=None, sa_column=Column(Text))
    growth_area: str | None = Field(default=None, sa_column=Column(Text))
    resume_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    resume_filename: str | None = Field(default=None, max_length=255)
    resume_hash: str | None = Field(default=None, max_length=64)
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


class AuditLog(SQLModel, table=True):
    """Append-only record of sensitive admin operations and system tasks."""

    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)
    # No FK on actor_user_id: audit rows must outlive the user they reference
    # (deleting a user must not cascade-delete their audit history).
    actor_user_id: int | None = Field(default=None, index=True)
    action: str = Field(index=True, max_length=64)
    target_type: str = Field(index=True, max_length=64)
    target_id: int = Field(index=True)
    detail: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ip_address: str | None = Field(default=None, max_length=45)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
