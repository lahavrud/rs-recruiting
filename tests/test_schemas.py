"""Tests for Pydantic schemas validation."""

import pytest
from pydantic import ValidationError

from src.schemas import (
    CandidateProfileCreate,
    JobAdminCreate,
    JobCreate,
    JobUpdate,
    RefreshRequest,
)


@pytest.mark.parametrize(
    "schema_class,create_kwargs,expected_path",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Test User",
                "email": "test@example.com",
                "phone": "050-000-0000",
                "resume_path": "uploads/resumes/test_resume.pdf",
            },
            "uploads/resumes/test_resume.pdf",
        ),
    ],
)
def test_valid_resume_path(schema_class, create_kwargs, expected_path):
    """Test that valid paths within uploads/resumes/ are accepted."""
    schema = schema_class(**create_kwargs)
    assert schema.resume_path == expected_path


@pytest.mark.parametrize(
    "schema_class,create_kwargs",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Test User",
                "email": "test@example.com",
                "phone": "050-000-0000",
                "resume_path": None,
            },
        ),
    ],
)
def test_none_resume_path(schema_class, create_kwargs):
    """Test that None is allowed for optional resume_path field."""
    schema = schema_class(**create_kwargs)
    assert schema.resume_path is None


@pytest.mark.parametrize(
    "schema_class,create_kwargs",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Malicious User",
                "email": "malicious@example.com",
                "phone": "050-000-0000",
                "resume_path": "../../../../etc/passwd",
            },
        ),
    ],
)
def test_path_traversal_parent_directory(schema_class, create_kwargs):
    """Test that paths with '..' are rejected (path traversal attack)."""
    with pytest.raises(
        ValidationError, match="Path cannot contain path traversal sequences"
    ):
        schema_class(**create_kwargs)


@pytest.mark.parametrize(
    "schema_class,create_kwargs",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Malicious User",
                "email": "malicious@example.com",
                "phone": "050-000-0000",
                "resume_path": "../config.py",
            },
        ),
    ],
)
def test_path_traversal_relative_parent(schema_class, create_kwargs):
    """Test that relative parent paths are rejected."""
    with pytest.raises(
        ValidationError, match="Path cannot contain path traversal sequences"
    ):
        schema_class(**create_kwargs)


@pytest.mark.parametrize(
    "schema_class,create_kwargs",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Malicious User",
                "email": "malicious@example.com",
                "phone": "050-000-0000",
                "resume_path": "/root/sensitive_file",
            },
        ),
    ],
)
def test_absolute_path_rejected(schema_class, create_kwargs):
    """Test that absolute paths are rejected."""
    with pytest.raises(ValidationError, match="Path cannot be absolute"):
        schema_class(**create_kwargs)


@pytest.mark.parametrize(
    "schema_class,create_kwargs",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Malicious User",
                "email": "malicious@example.com",
                "phone": "050-000-0000",
                "resume_path": "config/secrets.env",
            },
        ),
    ],
)
def test_path_outside_uploads_directory(schema_class, create_kwargs):
    """Test that paths outside uploads/resumes/ are accepted (validation simplified).

    Note: The validation no longer enforces the uploads/resumes/ directory structure
    as the service layer handles file uploads and sets resume_path automatically
    with UUID-based identifiers from the storage provider.
    """
    # Paths outside uploads/resumes/ are now accepted (as long as no path traversal)
    schema = schema_class(**create_kwargs)
    assert schema.resume_path == "config/secrets.env"


@pytest.mark.parametrize(
    "schema_class,create_kwargs,expected_path",
    [
        (
            CandidateProfileCreate,
            {
                "full_name": "Test User",
                "email": "test@example.com",
                "phone": "050-000-0000",
                "resume_path": "uploads/resumes/2026/01/resume.pdf",
            },
            "uploads/resumes/2026/01/resume.pdf",
        ),
    ],
)
def test_nested_valid_path(schema_class, create_kwargs, expected_path):
    """Test that nested paths within uploads/resumes/ are accepted."""
    schema = schema_class(**create_kwargs)
    assert schema.resume_path == expected_path


# ---------------------------------------------------------------------------
# Phone validation tests
# ---------------------------------------------------------------------------

BASE_CREATE = {
    "full_name": "Test User",
    "email": "test@example.com",
    "phone": "050-000-0000",
}


@pytest.mark.parametrize(
    "schema_class,phone,expected",
    [
        (CandidateProfileCreate, "0501234567", "0501234567"),
        (CandidateProfileCreate, "050-123-4567", "050-123-4567"),
        (CandidateProfileCreate, "050 123 4567", "050 123 4567"),
    ],
)
def test_valid_phone(schema_class, phone, expected):
    """Israeli mobile (10 digits starting with 05) — accepted in any common
    shape (spaces, dashes, parens)."""
    schema = schema_class(**{**BASE_CREATE, "phone": phone})
    assert schema.phone == expected


@pytest.mark.parametrize(
    "schema_class,phone,error_match",
    [
        (CandidateProfileCreate, "", "required"),
        (CandidateProfileCreate, "abc", "digits, spaces"),
        # 9 digits, looks Israeli but missing one — the bug that prompted
        # tightening from min-5-digits to a strict 05\\d{8} match.
        (CandidateProfileCreate, "051234567", "Israeli mobile"),
        # Landline (03) — no longer accepted; candidates must use a mobile.
        (CandidateProfileCreate, "(03) 123 4567", "Israeli mobile"),
        # International format — same number, but candidates must enter the
        # local form so we have a uniform shape downstream.
        (CandidateProfileCreate, "+972 50 123 4567", "Israeli mobile"),
    ],
)
def test_invalid_phone(schema_class, phone, error_match):
    """Test that invalid phone numbers are rejected."""
    with pytest.raises(ValidationError, match=error_match):
        schema_class(**{**BASE_CREATE, "phone": phone})


# ---------------------------------------------------------------------------
# LinkedIn URL validation tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "schema_class,url,expected",
    [
        (
            CandidateProfileCreate,
            "https://www.linkedin.com/in/johndoe",
            "https://www.linkedin.com/in/johndoe",
        ),
        (CandidateProfileCreate, None, None),
        (CandidateProfileCreate, "", None),
    ],
)
def test_valid_linkedin_url(schema_class, url, expected):
    """Test that valid LinkedIn URLs are accepted."""
    schema = schema_class(**{**BASE_CREATE, "linkedin_url": url})
    assert schema.linkedin_url == expected


@pytest.mark.parametrize(
    "schema_class,url,error_match",
    [
        # Wrong scheme (http is no longer accepted — https only)
        (CandidateProfileCreate, "http://linkedin.com/in/janedoe", "https"),
        (CandidateProfileCreate, "ftp://linkedin.com/in/foo", "https"),
        # Not a linkedin.com host (substring bypass attempt)
        (
            CandidateProfileCreate,
            "https://evil.com/linkedin.com/in/foo",
            "linkedin.com",
        ),
        # Missing scheme
        (CandidateProfileCreate, "linkedin.com/in/foo", "https"),
    ],
)
def test_invalid_linkedin_url(schema_class, url, error_match):
    """Test that invalid LinkedIn URLs are rejected."""
    with pytest.raises(ValidationError, match=error_match):
        schema_class(**{**BASE_CREATE, "linkedin_url": url})


# ── Job schemas: salary_min must be <= salary_max ─────────────────────────────


_JOB_BASE = {
    "title": "Backend Engineer",
    "short_description": "Backend role on the platform team.",
    "description": "Build services.",
    "requirements": [
        {"text": "Python fluency"},
        {"text": "FastAPI experience"},
        {"text": "PostgreSQL"},
    ],
    "location": "Tel Aviv",
}


@pytest.mark.parametrize(
    "schema_class, extra",
    [
        (JobCreate, {}),
        (JobAdminCreate, {"company_id": 1}),
    ],
)
def test_job_create_rejects_inverted_salary_range(schema_class, extra):
    """JobCreate / JobAdminCreate reject salary_min > salary_max."""
    with pytest.raises(ValidationError, match="salary_min must be <= salary_max"):
        schema_class(**_JOB_BASE, **extra, salary_min=30000, salary_max=20000)


def test_job_create_accepts_equal_salaries():
    """Equal salary_min and salary_max is a valid single-point range."""
    job = JobCreate(**_JOB_BASE, salary_min=20000, salary_max=20000)
    assert job.salary_min == job.salary_max == 20000


def test_job_update_rejects_inverted_salary_range_when_both_set():
    """JobUpdate enforces the range when both bounds are in the same payload."""
    with pytest.raises(ValidationError, match="salary_min must be <= salary_max"):
        JobUpdate(salary_min=30000, salary_max=20000)


def test_job_update_allows_partial_salary_change():
    """JobUpdate is OK when only one bound is set (DB CHECK guards the rest)."""
    JobUpdate(salary_min=25000)  # no salary_max in payload -> no schema check
    JobUpdate(salary_max=25000)  # symmetric


# ── RefreshRequest: max_length=512 on refresh_token ──────────────────────────


def test_refresh_request_accepts_token_at_limit():
    req = RefreshRequest(refresh_token="x" * 512)
    assert len(req.refresh_token) == 512


def test_refresh_request_rejects_token_over_limit():
    with pytest.raises(ValidationError):
        RefreshRequest(refresh_token="x" * 513)
