"""Email-quota model: a daily send counter (one row per calendar day)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Integer
from sqlmodel import Column, Field, SQLModel


class EmailQuota(SQLModel, table=True):
    """Daily email-send counter (one row per calendar day).

    Written via a raw-SQL upsert by the worker after each successful send
    (see ``core/services/email_quota.py``). Modeled here so SQLModel's
    ``create_all`` builds it in dev/test exactly as Alembic migration
    ``e03b8aa073a3`` builds it in production — keep the two in sync.
    """

    __tablename__ = "email_quota"

    # Attribute is `day` (a bare `date` field name clashes with the `date` type
    # under pydantic v2); the DB column is "date" to match migration e03b8aa073a3.
    day: date = Field(sa_column=Column("date", Date, primary_key=True, nullable=False))
    count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
