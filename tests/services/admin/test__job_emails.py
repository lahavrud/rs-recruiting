"""Unit tests for admin job-update company-notification emails."""

from unittest.mock import AsyncMock, patch

from rs_shared.models import CompanyProfile, Job, User
from rs_shared.services.admin._job_emails import notify_company_of_update

# queue_email writes the outbox row inside the caller's transaction, so these
# unit tests patch it out and assert on the arguments instead of a real row —
# the row-writing itself is covered in tests/core/services/test_email_outbox.py.
_PATCH_EMAIL = "rs_shared.services.admin._job_emails.queue_email"


def _job_with_user(email: str = "company@test.com") -> Job:
    job = Job(title="Backend Engineer", status="published")
    job.company = CompanyProfile(name="Acme")
    job.company.user = User(
        email=email,
        hashed_password="hashed",  # pragma: allowlist secret
    )
    return job


async def test_notify_company_of_update_sends_closure_email_when_closing():
    job = _job_with_user()
    session = AsyncMock()

    with patch(_PATCH_EMAIL, new_callable=AsyncMock) as mock_email:
        await notify_company_of_update(
            session,
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


async def test_notify_company_of_update_sends_update_email_for_other_field_changes():
    job = _job_with_user()
    session = AsyncMock()

    with patch(_PATCH_EMAIL, new_callable=AsyncMock) as mock_email:
        await notify_company_of_update(
            session,
            job,
            old_title="Backend Engineer",
            title_changed=False,
            changed_labels=["מיקום"],
            is_closing=False,
        )

    mock_email.assert_called_once()
    kwargs = mock_email.call_args.kwargs
    assert "עודכן" in kwargs["subject"]


async def test_notify_company_of_update_both_emails_when_closing_with_changes():
    job = _job_with_user()
    session = AsyncMock()

    with patch(_PATCH_EMAIL, new_callable=AsyncMock) as mock_email:
        await notify_company_of_update(
            session,
            job,
            old_title="Old Title",
            title_changed=True,
            changed_labels=["סטטוס", "כותרת"],
            is_closing=True,
        )

    subjects = [c.kwargs["subject"] for c in mock_email.call_args_list]
    assert any("נסגרה" in s for s in subjects)
    assert any("עודכן" in s for s in subjects)


async def test_notify_company_of_update_skips_when_company_has_no_user():
    job = Job(title="Backend Engineer", status="published")
    job.company = CompanyProfile(name="Orphan Co")
    job.company.user = None
    session = AsyncMock()

    with patch(_PATCH_EMAIL, new_callable=AsyncMock) as mock_email:
        await notify_company_of_update(
            session,
            job,
            old_title="Backend Engineer",
            title_changed=False,
            changed_labels=["מיקום"],
            is_closing=False,
        )

    mock_email.assert_not_called()


async def test_notify_company_of_update_no_email_when_nothing_relevant_changed():
    job = _job_with_user()
    session = AsyncMock()

    with patch(_PATCH_EMAIL, new_callable=AsyncMock) as mock_email:
        await notify_company_of_update(
            session,
            job,
            old_title="Backend Engineer",
            title_changed=False,
            changed_labels=[],
            is_closing=False,
        )

    mock_email.assert_not_called()
