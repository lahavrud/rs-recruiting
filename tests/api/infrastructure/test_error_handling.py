"""Unit tests for error handling utilities.

The HTTP ``detail`` field is now an *opaque error code* (e.g.
``"job_not_found"``) rather than the exception's stringified message,
which used to embed PII (email addresses) and internal IDs (issue #648).
"""

from fastapi import HTTPException, status

from rs_api.infrastructure.error_handling import service_exception_to_http
from rs_shared.services.exceptions import (
    AccountLockedError,
    CompanyNotFoundError,
    CompanyNotPendingError,
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
    JobCannotBeDeletedError,
    JobCannotBeUpdatedError,
    JobNotFoundError,
    JobNotOwnedByCompanyError,
    JobNotPendingError,
    MfaLockedError,
)


class TestServiceExceptionToHttp:
    """Tests for service_exception_to_http function."""

    def test_job_not_found_error_maps_to_404(self):
        http_exception = service_exception_to_http(JobNotFoundError("anything"))
        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_404_NOT_FOUND
        assert http_exception.detail == "job_not_found"

    def test_company_not_found_error_maps_to_404(self):
        http_exception = service_exception_to_http(CompanyNotFoundError("anything"))
        assert http_exception.status_code == status.HTTP_404_NOT_FOUND
        assert http_exception.detail == "company_not_found"

    def test_job_not_owned_by_company_error_maps_to_403(self):
        http_exception = service_exception_to_http(
            JobNotOwnedByCompanyError("anything")
        )
        assert http_exception.status_code == status.HTTP_403_FORBIDDEN
        assert http_exception.detail == "job_not_owned"

    def test_inactive_user_error_maps_to_401(self):
        http_exception = service_exception_to_http(InactiveUserError("anything"))
        assert http_exception.status_code == status.HTTP_401_UNAUTHORIZED
        assert http_exception.detail == "inactive_user"

    def test_invalid_credentials_error_maps_to_401(self):
        http_exception = service_exception_to_http(InvalidCredentialsError("anything"))
        assert http_exception.status_code == status.HTTP_401_UNAUTHORIZED
        assert http_exception.detail == "invalid_credentials"

    def test_job_cannot_be_updated_error_maps_to_400(self):
        http_exception = service_exception_to_http(JobCannotBeUpdatedError("anything"))
        assert http_exception.status_code == status.HTTP_400_BAD_REQUEST
        assert http_exception.detail == "job_cannot_be_updated"

    def test_job_cannot_be_deleted_error_maps_to_400(self):
        http_exception = service_exception_to_http(JobCannotBeDeletedError("anything"))
        assert http_exception.status_code == status.HTTP_400_BAD_REQUEST
        assert http_exception.detail == "job_cannot_be_deleted"

    def test_company_not_pending_error_maps_to_400(self):
        http_exception = service_exception_to_http(CompanyNotPendingError("anything"))
        assert http_exception.status_code == status.HTTP_400_BAD_REQUEST
        assert http_exception.detail == "company_not_pending"

    def test_job_not_pending_error_maps_to_400(self):
        http_exception = service_exception_to_http(JobNotPendingError("anything"))
        assert http_exception.status_code == status.HTTP_400_BAD_REQUEST
        assert http_exception.detail == "job_not_pending"

    def test_email_already_exists_does_not_leak_email(self):
        """Regression for issue #648 — the email must never appear in the
        HTTP detail. The exception message contains it for logs, but the
        response only carries the opaque code."""
        http_exception = service_exception_to_http(
            EmailAlreadyExistsError("victim@example.com")
        )
        assert http_exception.status_code == status.HTTP_409_CONFLICT
        assert http_exception.detail == "email_already_exists"
        # Defensive: assert the email is not in the rendered detail at all.
        assert "victim@example.com" not in str(http_exception.detail)

    def test_unmapped_exception_uses_default_status_and_generic_code(self):
        """Unmapped exceptions get the default status + a generic code so
        the response still carries a machine-readable handle."""
        http_exception = service_exception_to_http(ValueError("some leak"))
        assert http_exception.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert http_exception.detail == "internal_error"
        assert "some leak" not in str(http_exception.detail)

    def test_unmapped_exception_with_custom_default_status(self):
        custom_status = status.HTTP_418_IM_A_TEAPOT
        http_exception = service_exception_to_http(
            ValueError("some leak"), default_status=custom_status
        )
        assert http_exception.status_code == custom_status
        assert http_exception.detail == "internal_error"

    def test_exception_str_message_is_never_in_detail(self):
        """The detail must be the code, not a free-form message — that's
        the whole point of issue #648."""
        http_exception = service_exception_to_http(JobNotFoundError("internal id=42"))
        assert http_exception.detail == "job_not_found"
        assert "42" not in str(http_exception.detail)


def test_lock_errors_carry_retry_after_in_seconds():
    for exc in (AccountLockedError(3), MfaLockedError(10)):
        http = service_exception_to_http(exc)
        assert http.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert http.headers == {"Retry-After": str(exc.minutes_remaining * 60)}
    assert service_exception_to_http(JobNotFoundError("x")).headers is None
