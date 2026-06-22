"""JSON-LD builders for the SEO prerender endpoints.

All builders return plain dicts (no @context). Use ``encode_jsonld_graph``
from ``_render`` to wrap them in a single ``schema.org`` @graph for embedding
inside a ``<script type="application/ld+json">`` element.
"""

import html
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from src.models import Job

from ._articles import Article
from ._content import (
    JOB_POSTING_VALID_DAYS,
    JOBS_HEADLINE,
    SITE_NAME,
)


def description_html(job: Job) -> str:
    """Render description + requirements as HTML for JSON-LD.

    Google's JobPosting spec requires ``description`` to be HTML so paragraphs
    and bullet lists render in the rich result. Plain text with `\\n` does not.
    """
    parts: list[str] = []
    for paragraph in job.description.split("\n\n"):
        text = paragraph.strip()
        if text:
            parts.append(f"<p>{html.escape(text)}</p>")
    items = [
        f"<li>{html.escape(req['text'])}</li>"
        for req in job.requirements
        if isinstance(req, dict) and req.get("text")
    ]
    if items:
        parts.append("<ul>" + "".join(items) + "</ul>")
    return "".join(parts)


def job_posting(job: Job, site_url: str) -> dict:
    valid_through = job.created_at + timedelta(days=JOB_POSTING_VALID_DAYS)
    posting: dict[str, Any] = {
        "@type": "JobPosting",
        "title": job.title,
        "description": description_html(job),
        "datePosted": job.created_at.isoformat(),
        "validThrough": valid_through.isoformat(),
        "employmentType": "FULL_TIME",
        "directApply": True,
        "identifier": {
            "@type": "PropertyValue",
            "name": SITE_NAME,
            "value": str(job.id),
        },
        "url": f"{site_url}/jobs/{job.id}",
        "hiringOrganization": {
            "@type": "Organization",
            "name": SITE_NAME,
            "sameAs": site_url,
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": job.location,
                "addressCountry": "IL",
            },
        },
    }
    if job.salary_min and job.salary_max:
        posting["baseSalary"] = {
            "@type": "MonetaryAmount",
            "currency": "ILS",
            "value": {
                "@type": "QuantitativeValue",
                "minValue": job.salary_min,
                "maxValue": job.salary_max,
                "unitText": "MONTH",
            },
        }
    return posting


def site(site_url: str) -> list[dict]:
    """Organization + EmploymentAgency + WebSite — matches LandingPage SITE_SCHEMA.

    Shared @id between Organization and WebSite gives Google a single canonical
    brand entity for the domain (helps consolidate the homepage and /jobs into
    a single SERP entry).
    """
    return [
        {
            "@type": ["Organization", "EmploymentAgency"],
            "@id": f"{site_url}/#organization",
            "name": SITE_NAME,
            "url": site_url,
            "logo": f"{site_url}/logo.svg",
            "description": (
                "משרד גיוס והשמה בוטיקי המתמחה בגיוס לתפקידי ניהול ותפעול "
                "מבנים ונכסים בישראל"
            ),
            "areaServed": "IL",
            "knowsAbout": [
                "ניהול מבנים",
                "תפעול מבנים",
                "ניהול נכסים",
                "גיוס עובדים",
                "השמה",
            ],
            "contactPoint": {
                "@type": "ContactPoint",
                "email": "support@rs-recruiting.com",
                "contactType": "כוח אדם וגיוס",
                "areaServed": "IL",
                "availableLanguage": "Hebrew",
            },
        },
        {
            "@type": "WebSite",
            "@id": f"{site_url}/#website",
            "url": site_url,
            "name": SITE_NAME,
            "inLanguage": "he-IL",
            "publisher": {"@id": f"{site_url}/#organization"},
        },
    ]


def breadcrumb(items: Sequence[tuple[str, str]]) -> dict:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
            for i, (name, url) in enumerate(items)
        ],
    }


def article(item: Article, site_url: str) -> dict:
    """Article schema — matches ArticlePage.tsx so SPA + prerender agree."""
    canonical = f"{site_url}/articles/{item.slug}"
    payload: dict[str, Any] = {
        "@type": "Article",
        "headline": item.title,
        "description": item.description,
        "datePublished": item.date,
        "dateModified": item.date,
        "inLanguage": "he-IL",
        "mainEntityOfPage": canonical,
        "author": {"@type": "Organization", "name": SITE_NAME, "url": site_url},
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "logo": {"@type": "ImageObject", "url": f"{site_url}/logo.svg"},
        },
    }
    if item.image:
        payload["image"] = f"{site_url}{item.image}"
    if item.keywords:
        payload["keywords"] = item.keywords
    return payload


def item_list(jobs: list[Job], site_url: str) -> dict:
    return {
        "@type": "ItemList",
        "name": JOBS_HEADLINE,
        "url": f"{site_url}/jobs",
        "numberOfItems": len(jobs),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": j.title,
                "url": f"{site_url}/jobs/{j.id}",
            }
            for i, j in enumerate(jobs[:10])
        ],
    }
