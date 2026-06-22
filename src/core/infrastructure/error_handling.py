"""Error handling utilities for converting service exceptions to HTTP exceptions.

The HTTP ``detail`` field is an *opaque error code* (e.g. ``"job_not_found"``),
not the exception's stringified message. ``str(exception)`` historically
embedded user-supplied data — for example ``EmailAlreadyExistsError`` rendered
as ``"Email user@example.com is already registered"`` — which leaked PII and
internal identifiers back to anonymous callers. The codes are stable, short,
snake_case strings that the frontend maps to localised UI text via
``i18n.t()``.
"""

from fastapi import HTTPException, status

from src.services.exceptions import (
    AccountLockedError,
    ApplicationAlreadyEditableError,
    ApplicationAlreadyExistsError,
    ApplicationAlreadyLockedError,
    ApplicationNotEditableError,
    ApplicationNotFoundError,
    CandidateNotFoundError,
    CompanyNotFoundError,
    CompanyNotPendingError,
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidActivationTokenError,
    InvalidApplicationStatusTransitionError,
    InvalidCredentialsError,
    InvalidCursorError,
    InvalidInviteTokenError,
    InvalidPasswordResetTokenError,
    InviteAlreadyRevokedError,
    InviteNotFoundError,
    InvitePendingForEmailError,
    JobCannotBeDeletedError,
    JobCannotBeUpdatedError,
    JobNotFoundError,
    JobNotOwnedByCompanyError,
    JobNotPendingError,
    PendingActivationError,
    PendingApprovalError,
)

# Mapping of service exceptions to HTTP status codes
EXCEPTION_STATUS_MAP: dict[type[Exception], int] = {
    # Not found errors (404)
    JobNotFoundError: status.HTTP_404_NOT_FOUND,
    CompanyNotFoundError: status.HTTP_404_NOT_FOUND,
    ApplicationNotFoundError: status.HTTP_404_NOT_FOUND,
    CandidateNotFoundError: status.HTTP_404_NOT_FOUND,
    # Conflict errors (409)
    ApplicationAlreadyExistsError: status.HTTP_409_CONFLICT,
    ApplicationAlreadyEditableError: status.HTTP_409_CONFLICT,
    ApplicationAlreadyLockedError: status.HTTP_409_CONFLICT,
    ApplicationNotEditableError: status.HTTP_409_CONFLICT,
    InvitePendingForEmailError: status.HTTP_409_CONFLICT,
    EmailAlreadyExistsError: status.HTTP_409_CONFLICT,
    # Forbidden errors (403)
    JobNotOwnedByCompanyError: status.HTTP_403_FORBIDDEN,
    # Bad request — invalid activation token
    InvalidActivationTokenError: status.HTTP_400_BAD_REQUEST,
    InvalidPasswordResetTokenError: status.HTTP_400_BAD_REQUEST,
    # Unauthorized errors (401) — all login failures return 401 regardless of
    # account state, so HTTP status code alone cannot confirm registration.
    InvalidCredentialsError: status.HTTP_401_UNAUTHORIZED,
    InactiveUserError: status.HTTP_401_UNAUTHORIZED,
    PendingApprovalError: status.HTTP_401_UNAUTHORIZED,
    PendingActivationError: status.HTTP_401_UNAUTHORIZED,
    # Too many requests (429)
    AccountLockedError: status.HTTP_429_TOO_MANY_REQUESTS,
    # Bad request errors (400)
    InvalidInviteTokenError: status.HTTP_400_BAD_REQUEST,
    InviteAlreadyRevokedError: status.HTTP_400_BAD_REQUEST,
    # Not found (404)
    InviteNotFoundError: status.HTTP_404_NOT_FOUND,
    JobCannotBeUpdatedError: status.HTTP_400_BAD_REQUEST,
    JobCannotBeDeletedError: status.HTTP_400_BAD_REQUEST,
    CompanyNotPendingError: status.HTTP_400_BAD_REQUEST,
    JobNotPendingError: status.HTTP_400_BAD_REQUEST,
    InvalidApplicationStatusTransitionError: status.HTTP_400_BAD_REQUEST,
    InvalidCursorError: status.HTTP_400_BAD_REQUEST,
}

# Stable, opaque error codes returned in the HTTP ``detail`` field. The
# frontend maps these to localised user-facing strings; backends never
# emit ``str(exception)`` here because exception messages contain
# user-supplied data (emails, internal IDs) that would otherwise leak via
# the HTTP response.
EXCEPTION_CODE_MAP: dict[type[Exception], str] = {
    # Not found
    JobNotFoundError: "job_not_found",
    CompanyNotFoundError: "company_not_found",
    ApplicationNotFoundError: "application_not_found",
    CandidateNotFoundError: "candidate_not_found",
    InviteNotFoundError: "invite_not_found",
    # Conflict
    ApplicationAlreadyExistsError: "already_applied",
    ApplicationAlreadyEditableError: "already_applied_editable",
    ApplicationAlreadyLockedError: "already_applied_locked",
    ApplicationNotEditableError: "application_not_editable",
    InvitePendingForEmailError: "invite_pending",
    EmailAlreadyExistsError: "email_already_exists",
    # Forbidden
    JobNotOwnedByCompanyError: "job_not_owned",
    # Token / credential issues
    InvalidActivationTokenError: "invalid_activation_token",
    InvalidPasswordResetTokenError: (
        "invalid_password_reset_token"  # pragma: allowlist secret
    ),
    InvalidCredentialsError: "invalid_credentials",
    InactiveUserError: "inactive_user",
    PendingApprovalError: "pending_approval",
    PendingActivationError: "account_pending_activation",
    # Lockout
    AccountLockedError: "account_locked",
    # Invite lifecycle
    InvalidInviteTokenError: "invalid_invite_token",
    InviteAlreadyRevokedError: "invite_revoked",
    # State machine
    JobCannotBeUpdatedError: "job_cannot_be_updated",
    JobCannotBeDeletedError: "job_cannot_be_deleted",
    CompanyNotPendingError: "company_not_pending",
    JobNotPendingError: "job_not_pending",
    InvalidApplicationStatusTransitionError: "invalid_status_transition",
    # Pagination
    InvalidCursorError: "invalid_cursor",
}


def service_exception_to_http(
    exception: Exception,
    default_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
) -> HTTPException:
    """Convert a service exception to an ``HTTPException`` with an opaque code.

    The returned ``detail`` is the mapped error code (e.g. ``"job_not_found"``)
    — never ``str(exception)`` — so user-supplied data the service layer
    interpolates into exception messages doesn't end up in the HTTP body.
    Falls back to ``"internal_error"`` for unmapped types so the response
    still carries a useful machine-readable handle.
    """
    exc_type = type(exception)
    status_code = EXCEPTION_STATUS_MAP.get(exc_type, default_status)
    code = EXCEPTION_CODE_MAP.get(exc_type, "internal_error")
    return HTTPException(status_code=status_code, detail=code)
