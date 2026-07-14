"""Actor entities: User and its two 1:1 profiles (company, candidate).

The three are co-located in one module on purpose: their ``Relationship``
back-references form a cycle (``User`` ↔ ``CompanyProfile``, ``User`` ↔
``CandidateProfile``), and under ``from __future__ import annotations`` SQLModel
resolves each bare-class relationship annotation against *this module's*
namespace. Splitting them would need circular imports; keeping them together
keeps the forward-refs resolvable without one.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from pydantic import field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlmodel import Column, Field, Relationship, SQLModel

from rs_shared.core.infrastructure.config import settings
from rs_shared.enums import UserRole

# Embedding vector width for the resume-matching engine. Fixed at the DB-column
# level by the migration — keep in lockstep with ``settings.embedding_dim`` and
# the embedding model's output dimension (see core/services/embeddings.py).
_EMBEDDING_DIM = settings.embedding_dim


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
    sessions_invalidated_at: datetime | None = Field(
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
    # Plain text extracted from the resume file (Hebrew/English/mixed) and the
    # multilingual embedding of it, populated by ``match_candidate_task`` on CV
    # upload/update. NULL until first matched; cleared on resume removal.
    parsed_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    # One-line Hebrew LLM summary of the resume, generated alongside the
    # embedding by ``match_candidate_task``. NULL until first processed.
    resume_summary: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(_EMBEDDING_DIM), nullable=True),
    )
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
