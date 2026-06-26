"""Enumerations used across the application.

This module contains all enum types shared between models, schemas, and services.
Keeping enums separate avoids circular dependencies and maintains clean architecture.
"""

from enum import Enum


class UserRole(str, Enum):
    """User role enumeration."""

    ADMIN = "ADMIN"
    COMPANY = "COMPANY"
    CANDIDATE = "CANDIDATE"


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING_APPROVAL = "PENDING_APPROVAL"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"


class ApplicationStatus(str, Enum):
    """Application (Match) status enumeration."""

    NEW = "NEW"
    APPROVED_BY_ADMIN = "APPROVED_BY_ADMIN"
    REJECTED = "REJECTED"
    HIRED = "HIRED"
    WITHDRAWN = "WITHDRAWN"
    JOB_CLOSED = "JOB_CLOSED"


class InviteTokenStatus(str, Enum):
    """Invite token lifecycle status."""

    PENDING = "PENDING"
    USED = "USED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class MatchSuggestionStatus(str, Enum):
    """Admin decision on an AI-generated match suggestion."""

    DISMISSED = "DISMISSED"
    PUSHED = "PUSHED"
