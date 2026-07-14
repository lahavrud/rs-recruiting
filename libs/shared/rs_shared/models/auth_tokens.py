"""Single-use, hashed token rows keyed to a user.

All of these persist a SHA-256 ``token_hash`` (the raw token only ever lives in
an email link) and reference ``user.id``. None carry a SQLModel ``Relationship``
— they join to ``User`` via plain queries — so this module has no cross-model
imports. ``DataExportRequest`` (the GDPR export download token) lives here too:
it is the same single-use signed-token shape.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlmodel import Column, Field, SQLModel

from rs_shared.enums import InviteTokenStatus


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
    user_agent: str | None = Field(default=None, max_length=512)
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
