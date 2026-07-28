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
    """Application (Match) status enumeration.

    The lifecycle (in pipeline order):

        PENDING_ADMIN_REVIEW → APPROVED_BY_ADMIN → INTERVIEWING → OFFER → HIRED
                                                                → REJECTED_BY_COMPANY
        PENDING_ADMIN_REVIEW / APPROVED_BY_ADMIN → REJECTED_BY_ADMIN
                                                     (RS screen-out, pre-employer)
        any active → WITHDRAWN (candidate) / JOB_CLOSED (admin closes the job)

    Rejection is split by actor: ``REJECTED_BY_ADMIN`` is an RS screen-out
    before the employer ever sees the candidate; ``REJECTED_BY_COMPANY`` is an
    employer's decline after review. The semantic groupings below
    (``is_terminal`` / ``is_active`` / ``company_visible`` / ``company_settable``
    / ``sort_weight``) are the single source of truth — derive from them rather
    than re-listing statuses at each call site.
    """

    PENDING_ADMIN_REVIEW = "PENDING_ADMIN_REVIEW"
    APPROVED_BY_ADMIN = "APPROVED_BY_ADMIN"
    INTERVIEWING = "INTERVIEWING"
    OFFER = "OFFER"
    HIRED = "HIRED"
    REJECTED_BY_COMPANY = "REJECTED_BY_COMPANY"
    REJECTED_BY_ADMIN = "REJECTED_BY_ADMIN"
    WITHDRAWN = "WITHDRAWN"
    JOB_CLOSED = "JOB_CLOSED"

    @property
    def is_active(self) -> bool:
        """Pre-decision — still in flight, counts against a job close."""
        return self in _ACTIVE_STATUSES

    @property
    def is_terminal(self) -> bool:
        """A final outcome — no further transitions expected."""
        return self in _TERMINAL_STATUSES

    @property
    def company_visible(self) -> bool:
        """Surfaced to the employer (post-push states only)."""
        return self in _COMPANY_VISIBLE_STATUSES

    @property
    def company_settable(self) -> bool:
        """The employer may move an application into this status."""
        return self in _COMPANY_SETTABLE_STATUSES

    @property
    def sort_weight(self) -> int:
        """Display ordering for status-grouped lists (pipeline order)."""
        return _STATUS_SORT_ORDER.index(self)


# Pipeline order — drives ``sort_weight`` and the migration's enum definition.
_STATUS_SORT_ORDER: tuple[ApplicationStatus, ...] = (
    ApplicationStatus.PENDING_ADMIN_REVIEW,
    ApplicationStatus.APPROVED_BY_ADMIN,
    ApplicationStatus.INTERVIEWING,
    ApplicationStatus.OFFER,
    ApplicationStatus.HIRED,
    ApplicationStatus.REJECTED_BY_COMPANY,
    ApplicationStatus.REJECTED_BY_ADMIN,
    ApplicationStatus.WITHDRAWN,
    ApplicationStatus.JOB_CLOSED,
)

_ACTIVE_STATUSES: frozenset[ApplicationStatus] = frozenset(
    {
        ApplicationStatus.PENDING_ADMIN_REVIEW,
        ApplicationStatus.APPROVED_BY_ADMIN,
        ApplicationStatus.INTERVIEWING,
        ApplicationStatus.OFFER,
    }
)

_TERMINAL_STATUSES: frozenset[ApplicationStatus] = frozenset(
    {
        ApplicationStatus.HIRED,
        ApplicationStatus.REJECTED_BY_COMPANY,
        ApplicationStatus.REJECTED_BY_ADMIN,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.JOB_CLOSED,
    }
)

_COMPANY_VISIBLE_STATUSES: frozenset[ApplicationStatus] = frozenset(
    {
        ApplicationStatus.APPROVED_BY_ADMIN,
        ApplicationStatus.INTERVIEWING,
        ApplicationStatus.OFFER,
        ApplicationStatus.HIRED,
        ApplicationStatus.REJECTED_BY_COMPANY,
    }
)

_COMPANY_SETTABLE_STATUSES: frozenset[ApplicationStatus] = frozenset(
    {
        ApplicationStatus.INTERVIEWING,
        ApplicationStatus.OFFER,
        ApplicationStatus.HIRED,
        ApplicationStatus.REJECTED_BY_COMPANY,
    }
)

# Query-ready ordering of the active group, for SQL ``IN`` clauses and anywhere
# else a sequence is needed. Derived from ``is_active`` so it cannot drift, and
# ordered by the pipeline so generated SQL is stable and readable. Import this
# rather than re-deriving it per call site.
ACTIVE_APPLICATION_STATUSES: tuple[ApplicationStatus, ...] = tuple(
    s for s in _STATUS_SORT_ORDER if s in _ACTIVE_STATUSES
)


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


class EmailStatus(str, Enum):
    """Lifecycle of an ``EmailOutbox`` row.

        PENDING → SENDING → SENT
                          → FAILED    (permanent — will not be retried)
                  SENDING → PENDING   (transient failure; SQS redelivers)

    SENDING is the crash-window marker: a row left in SENDING may or may not
    have reached the provider, so the worker refuses to resend it rather than
    risk a duplicate. See ``models/email_outbox.py``.
    """

    PENDING = "PENDING"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
