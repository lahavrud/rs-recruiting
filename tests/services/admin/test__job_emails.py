"""Unit tests for admin job-update company-notification emails."""

from unittest.mock import patch

from src.models import CompanyProfile, Job, User
from src.services.admin._job_emails import notify_company_of_update

_PATCH_EMAIL = "src.services.admin._job_emails.enqueue_email_task"
_PATCH_DEFER = "src.services.admin._job_emails.defer_after_commit"


def _job_with_user(email: str = "company@test.com") -> Job:
    job = Job(title="Backend Engineer", status="published")
    job.company = CompanyProfile(name="Acme")
    job.company.user = User(
        email=email,
        hashed_password="hashed",  # pragma: allowlist secret
    )
    return job


def test_notify_company_of_update_sends_closure_email_when_closing():
    job = _job_with_user()

    with (
        patch(_PATCH_EMAIL) as mock_email,
        patch(_PATCH_DEFER, side_effect=lambda fn: fn()),
    ):
        notify_company_of_update(
            job,
            old_title="Backend Engineer",
            title_changed=False,
            changed_labels=["סטטוס"],
            is_closing=True,
        )

    mock_email.assert_called_once()
    kwargs = mock_email.call_args.kwargs
    assert kwargs["to"] == "company@test.com"
    assert "נסגרה" in kwargs["subject"]


def test_notify_company_of_update_sends_update_email_for_other_field_changes():
    job = _job_with_user()

    with (
        patch(_PATCH_EMAIL) as mock_email,
        patch(_PATCH_DEFER, side_effect=lambda fn: fn()),
    ):
        notify_company_of_update(
            job,
            old_title="Backend Engineer",
            title_changed=False,
            changed_labels=["מיקום"],
            is_closing=False,
        )

    mock_email.assert_called_once()
    kwargs = mock_email.call_args.kwargs
    assert "עודכן" in kwargs["subject"]


def test_notify_company_of_update_sends_both_emails_when_closing_with_other_changes():
    job = _job_with_user()

    with (
        patch(_PATCH_EMAIL) as mock_email,
        patch(_PATCH_DEFER, side_effect=lambda fn: fn()),
    ):
        notify_company_of_update(
            job,
            old_title="Old Title",
            title_changed=True,
            changed_labels=["סטטוס", "כותרת"],
            is_closing=True,
        )

    subjects = [c.kwargs["subject"] for c in mock_email.call_args_list]
    assert any("נסגרה" in s for s in subjects)
    assert any("עודכן" in s for s in subjects)


def test_notify_company_of_update_skips_when_company_has_no_user():
    job = Job(title="Backend Engineer", status="published")
    job.company = CompanyProfile(name="Orphan Co")
    job.company.user = None

    with (
        patch(_PATCH_EMAIL) as mock_email,
        patch(_PATCH_DEFER, side_effect=lambda fn: fn()),
    ):
        notify_company_of_update(
            job,
            old_title="Backend Engineer",
            title_changed=False,
            changed_labels=["מיקום"],
            is_closing=False,
        )

    mock_email.assert_not_called()


def test_notify_company_of_update_no_email_when_nothing_relevant_changed():
    job = _job_with_user()

    with (
        patch(_PATCH_EMAIL) as mock_email,
        patch(_PATCH_DEFER, side_effect=lambda fn: fn()),
    ):
        notify_company_of_update(
            job,
            old_title="Backend Engineer",
            title_changed=False,
            changed_labels=[],
            is_closing=False,
        )

    mock_email.assert_not_called()
