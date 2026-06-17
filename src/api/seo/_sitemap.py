"""robots.txt + sitemap.xml routes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import get_session
from src.services.public.jobs import list_published_job_sitemap_entries

from ._articles import list_articles
from ._content import DISALLOWED_PATHS

router = APIRouter()

_SITEMAP_HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
_SITEMAP_FOOTER = "</urlset>"


def _url_entry(loc: str, lastmod: str | None = None, changefreq: str = "weekly") -> str:
    mod = f"  <lastmod>{lastmod}</lastmod>\n" if lastmod else ""
    freq = f"  <changefreq>{changefreq}</changefreq>\n"
    return f"  <url>\n  <loc>{loc}</loc>\n{mod}{freq}  </url>\n"


@router.api_route(
    "/robots.txt",
    methods=["GET", "HEAD"],
    response_class=PlainTextResponse,
    include_in_schema=False,
)
async def robots_txt() -> str:
    # `Sitemap:` is a top-level directive that applies to the whole file, not
    # to any one user-agent group. Lighthouse's robots.txt validator flags it
    # as invalid when it appears inside a group without a blank-line separator.
    sitemap_url = f"{settings.frontend_base_url}/sitemap.xml"
    disallow = "\n".join(f"Disallow: {p}" for p in DISALLOWED_PATHS)
    return f"User-agent: *\nAllow: /\n{disallow}\n\nSitemap: {sitemap_url}\n"


@router.api_route(
    "/sitemap.xml",
    methods=["GET", "HEAD"],
    response_class=PlainTextResponse,
    include_in_schema=False,
)
async def sitemap_xml(session: AsyncSession = Depends(get_session)) -> str:
    base = settings.frontend_base_url
    today = datetime.now(UTC).date().isoformat()

    jobs = await list_published_job_sitemap_entries(session)

    entries = _url_entry(f"{base}/", changefreq="monthly")
    entries += _url_entry(f"{base}/jobs", lastmod=today, changefreq="daily")
    entries += _url_entry(f"{base}/about", changefreq="monthly")
    entries += _url_entry(f"{base}/contact", changefreq="yearly")
    entries += _url_entry(f"{base}/articles", changefreq="weekly")
    for item in list_articles():
        entries += _url_entry(
            f"{base}/articles/{item.slug}",
            lastmod=item.date,
            changefreq="monthly",
        )
    for job_id, updated_at in jobs:
        lastmod = updated_at.date().isoformat() if updated_at else today
        entries += _url_entry(f"{base}/jobs/{job_id}", lastmod=lastmod)

    return _SITEMAP_HEADER + entries + _SITEMAP_FOOTER
