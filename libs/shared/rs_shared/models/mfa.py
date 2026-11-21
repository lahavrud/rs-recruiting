"""Second-factor (TOTP) state: per-user secret, recovery codes, login challenges.

Policy lives in ``services/auth/mfa.py``. None of these carry a SQLModel
``Relationship``; they join to ``User`` by plain queries, like the token rows in
``auth_tokens.py``. Every FK cascades so deleting a user removes its MFA state.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlmodel import Column, Field, SQLModel


class UserMfa(SQLModel, table=True):
    """A user's TOTP enrolment. One row per user at most.

    ``enabled_at`` is NULL while enrolment is pending (secret issued, not yet
    confirmed with a code); only a non-NULL row means MFA is on.
    ``last_used_step`` is the highest TOTP time-step accepted so far: a code
    for that step or an earlier one is a replay and is refused.
    """

    __tablename__ = "user_mfa"

    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    # Fernet ciphertext of the base32 secret (security.encrypt_mfa_secret);
    # the plaintext is never stored.
    secret_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    enabled_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_used_step: int = Field(
        default=0,
        sa_column=Column(BigInteger, nullable=False, server_default="0"),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MfaRecoveryCode(SQLModel, table=True):
    """One single-use recovery code, stored only as a SHA-256 hash."""

    __tablename__ = "mfa_recovery_code"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    code_hash: str = Field(sa_column=Column(String(64), nullable=False, unique=True))
    used_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class MfaChallenge(SQLModel, table=True):
    """The pending second step of a login: password already verified.

    Single-use (deleted on success), short-lived, and dead after a few bad
    codes. Carries ``remember_me`` from the password step so the refresh cookie
    issued after the code matches what the user asked for.
    """

    __tablename__ = "mfa_challenge"

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(sa_column=Column(String(64), nullable=False, unique=True))
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    failed_attempts: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    remember_me: bool = Field(default=False)
