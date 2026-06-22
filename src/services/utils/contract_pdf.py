"""Generate a signed contract PDF by overlaying company details on the template."""

import asyncio
import io
import logging
from datetime import datetime

import aioboto3
import fitz  # pymupdf

from src.core.infrastructure.config import settings

logger = logging.getLogger(__name__)

# PDF page: 596 × 842 pt (A4).  All coordinates verified via get_text("dict").
#
# Document fonts (from get_fonts()):
#   Arial-BoldMT  14pt — title
#   ArialMT       11pt — body / לבין labels
#   Calibri       11pt — blank underlines and body
#   Arial-BoldMT  10pt — signature labels
#
# Drawn signature lines: y=672  (RS: x=358–518 | Company: x=54–232)
#
# Strategy: insert text DIRECTLY ON the underlines (no white-box erasure).
# This is how typewritten contracts look — the typed characters sit on top
# of the underline, which is the professional expected appearance.

# ── Date ─────────────────────────────────────────────────────────────────────
# Blank "_______________" at x=131–213, y=77–88 (just left of "מתאריך")
# We use a textbox so right-alignment pushes the date flush against "מתאריך".
_DATE_RECT = fitz.Rect(131, 76, 213, 90)

# ── Company info — each blank targeted individually ───────────────────────────
# These rects cover the underline spans precisely so text sits on them.
_NAME_RECT = fitz.Rect(417, 174, 499, 188)  # company name blank
_ID_RECT = fitz.Rect(309, 174, 381, 188)  # ח.פ number blank
_ADDR_RECT = fitz.Rect(193, 174, 264, 188)  # address blank

# ── Signatures ────────────────────────────────────────────────────────────────
# Lines are drawn at y=672.  Images positioned so they sit on those lines
# (bottom of image rect = y=672, giving ~40pt height above the line).
_RS_SIG_RECT = fitz.Rect(358, 632, 518, 672)  # right side — רוני רודיק
_COMPANY_SIG_RECT = fitz.Rect(54, 632, 232, 672)  # left side  — נציג החברה


async def _fetch_asset(key: str) -> bytes:
    """Fetch a static asset.

    Local mode: resolves relative to local_storage_path (copy files there for dev).
    S3 mode: fetches from the configured S3 bucket.
    """
    if settings.storage_provider != "s3":
        import asyncio
        from pathlib import Path

        local_path = Path(settings.local_storage_path) / key
        loop = asyncio.get_event_loop()
        exists = await loop.run_in_executor(None, local_path.exists)
        if not exists:
            raise FileNotFoundError(
                f"Asset not found at {local_path}. "
                f"Copy {key} into {settings.local_storage_path}/ for local dev."
            )
        return await loop.run_in_executor(None, local_path.read_bytes)

    session = aioboto3.Session()
    bucket = settings.aws_s3_bucket_name
    async with session.client(  # type: ignore[attr-defined]  # aioboto3 session.client() is untyped; stubs incomplete
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        endpoint_url=settings.aws_s3_endpoint_url,
    ) as s3:
        resp = await s3.get_object(Bucket=bucket, Key=key)
        return await resp["Body"].read()


def _htmlbox_rtl(page: fitz.Page, rect: fitz.Rect, text: str, size: float = 11) -> None:
    """Insert Hebrew RTL text via htmlbox — handles BiDi correctly."""
    html = (
        f'<div style="font-family:Helvetica,Arial,sans-serif;font-size:{size}pt;'
        f'color:#000000;direction:rtl;text-align:right;">{text}</div>'
    )
    page.insert_htmlbox(rect, html)


def _render_pdf(
    template_bytes: bytes,
    rs_sig_bytes: bytes,
    company_name: str,
    company_id: str,
    address: str,
    signed_at: datetime,
    company_signature_png_bytes: bytes,
) -> bytes:
    """CPU-bound PDF rendering — must be called via asyncio.to_thread."""
    from zoneinfo import ZoneInfo

    doc = fitz.open(stream=template_bytes, filetype="pdf")
    page = doc[0]

    # ── Date (right-aligned, LTR numbers flush against "מתאריך") ──────────────
    # Convert UTC timestamp to Israel time (UTC+3 in summer, UTC+2 in winter)
    # before formatting so the printed date matches what the user saw locally.
    israel = ZoneInfo("Asia/Jerusalem")
    date_str = signed_at.astimezone(israel).strftime("%-d/%-m/%Y")
    page.insert_htmlbox(
        _DATE_RECT,
        f'<div style="font-family:Helvetica,Arial,sans-serif;font-size:11pt;'
        f'color:#000000;direction:ltr;text-align:right;">{date_str}</div>',
    )

    # ── Company name (right-aligned Hebrew/LTR in its blank) ─────────────────
    _htmlbox_rtl(page, _NAME_RECT, company_name, size=10)

    # ── ח.פ number (LTR numeric, right-aligned to flush with blank edge) ──────
    page.insert_htmlbox(
        _ID_RECT,
        f'<div style="font-family:Helvetica,Arial,sans-serif;font-size:10pt;'
        f'color:#000000;direction:ltr;text-align:right;">{company_id}</div>',
    )

    # ── Address (right-aligned in its blank, smaller to fit) ──────────────────
    _htmlbox_rtl(page, _ADDR_RECT, address, size=9)

    # ── RS agency signature (sits on the drawn line at y=672) ─────────────────
    page.insert_image(_RS_SIG_RECT, stream=rs_sig_bytes, keep_proportion=True)

    # ── Company signature (sits on the drawn line at y=672) ───────────────────
    page.insert_image(
        _COMPANY_SIG_RECT,
        stream=company_signature_png_bytes,
        keep_proportion=True,
    )

    buf = io.BytesIO()
    doc.save(buf, deflate=True)
    return buf.getvalue()


async def generate_signed_contract(
    company_name: str,
    company_id: str,
    address: str,
    signed_at: datetime,
    company_signature_png_bytes: bytes,
) -> bytes:
    """Overlay company details and signatures on the RS contract template.

    Text is inserted DIRECTLY on the printed underlines (no white-box
    erasure), matching the appearance of a typewritten contract.
    Signatures are placed so their baseline sits on the drawn signature lines.

    Returns raw PDF bytes suitable for email attachment.
    """
    template_bytes = await _fetch_asset(settings.rs_contract_template_s3_key)
    rs_sig_bytes = await _fetch_asset(settings.rs_signature_s3_key)

    return await asyncio.to_thread(
        _render_pdf,
        template_bytes,
        rs_sig_bytes,
        company_name,
        company_id,
        address,
        signed_at,
        company_signature_png_bytes,
    )
