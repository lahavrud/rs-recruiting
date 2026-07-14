"""Database models (SQLModel ORM).

Split by domain into submodules that mirror ``schemas/``. Everything is
re-exported here so ``from rs_shared.models import User`` (and
``from rs_shared.models import SQLModel`` for ``metadata``) keep working
unchanged, and so importing this package registers *every* table on
``SQLModel.metadata`` — the dev/test/local schema is built by
``SQLModel.metadata.create_all`` (see ``core/infrastructure/database.py`` and
``rules/migrations.md``: every table needs a model importable at
``create_all`` time).

Import order matters only in that each submodule imports the sibling classes its
relationships reference; importing this package pulls them all in.
"""

from sqlmodel import SQLModel

from rs_shared.models.applications import Application
from rs_shared.models.audit import AuditLog
from rs_shared.models.auth_tokens import (
    ActivationToken,
    DataExportRequest,
    InviteToken,
    PasswordResetToken,
    RefreshToken,
    UsedRefreshToken,
)
from rs_shared.models.identity import CandidateProfile, CompanyProfile, User
from rs_shared.models.jobs import Job
from rs_shared.models.matching import MatchSuggestion
from rs_shared.models.quota import EmailQuota

__all__ = [
    "SQLModel",
    # identity
    "User",
    "CompanyProfile",
    "CandidateProfile",
    # jobs / applications / matching
    "Job",
    "Application",
    "MatchSuggestion",
    # auth tokens
    "InviteToken",
    "ActivationToken",
    "RefreshToken",
    "UsedRefreshToken",
    "PasswordResetToken",
    "DataExportRequest",
    # audit / quota
    "AuditLog",
    "EmailQuota",
]
