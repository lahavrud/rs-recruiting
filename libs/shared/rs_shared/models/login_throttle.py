"""Login throttle model: failed-login counters per (email, client IP).

Replaces the per-account ``User.failed_login_attempts`` / ``locked_until``
lockout, which let anyone who knew an email lock its owner out from anywhere.
Keyed by the *pair* so a source that keeps failing is slowed down without
affecting the same account from other addresses. See
``services/auth/login_throttle.py`` for the policy.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlmodel import Column, Field, SQLModel


class LoginThrottle(SQLModel, table=True):
    """Failed-login state for one (email, client IP) pair.

    Rows exist for unknown emails too (no FK to ``user``), so the throttle
    behaves identically whether or not an account exists. The email is stored
    only as a keyed hash. Rows are deleted on a successful login from the pair,
    on password reset (all of the email's rows), and by the nightly cleanup
    once they've been quiet for a day.
    """

    __tablename__ = "login_throttle"
    __table_args__ = (
        # Upsert target, and its leftmost prefix serves the per-email lookups
        # (cross-IP backstop sum, clear-all on password reset).
        UniqueConstraint(
            "email_hash", "client_ip", name="uq_login_throttle_email_hash_client_ip"
        ),
        # Nightly cleanup deletes by staleness.
        Index("ix_login_throttle_last_failure_at", "last_failure_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    # HMAC-SHA256 hex of the normalized email (never the email itself).
    email_hash: str = Field(sa_column=Column(String(64), nullable=False))
    # client_ip() result, or "unknown" when the request had no address.
    client_ip: str = Field(sa_column=Column(String(45), nullable=False))
    failures: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    last_failure_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    blocked_until: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
