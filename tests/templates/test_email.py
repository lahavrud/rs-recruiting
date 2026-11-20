"""Tests for HTML email template builders."""

from rs_shared.templates.email import (
    build_admin_application_digest_html,
    build_approval_html,
    build_invite_html,
)


def test_build_invite_html_contains_url():
    url = "https://example.com/register?token=abc123"
    html = build_invite_html(url)
    assert url in html
    assert "RS" in html
    assert 'dir="rtl"' in html


def test_build_invite_html_with_contact_name():
    html = build_invite_html("https://example.com", contact_name="ישראל")
    assert "ישראל" in html


def test_build_approval_html_contains_company_and_url():
    url = "https://example.com/activate?token=xyz"
    html = build_approval_html("חברת בדיקה", url)
    assert "חברת בדיקה" in html
    assert url in html
    assert 'dir="rtl"' in html


def test_build_admin_application_digest_html_lists_jobs_and_overflow():
    html = build_admin_application_digest_html(
        total=13,
        jobs=[
            {
                "title": "Backend <Engineer>",
                "company_name": "Acme",
                "count": 12,
                "applicants": [
                    {"name": "Dana Levi", "status_label": "ממתין לבדיקה"},
                ],
                "more": 11,
            },
            {
                "title": "Designer",
                "company_name": "Beta",
                "count": 1,
                "applicants": [{"name": "Noa Cohen", "status_label": "נדחה"}],
                "more": 0,
            },
        ],
        admin_url="https://rs.test/login?redirect=/admin/applications",
    )

    assert 'dir="rtl"' in html
    assert "13" in html
    assert "Backend &lt;Engineer&gt;" in html  # autoescaped
    assert "Dana Levi" in html and "Noa Cohen" in html
    assert "ועוד 11" in html
    assert "ועוד 0" not in html
    assert "https://rs.test/login?redirect=/admin/applications" in html
