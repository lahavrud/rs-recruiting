"""Tests for contract PDF generation service."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch


async def test_generate_signed_contract_returns_pdf_bytes():
    """generate_signed_contract overlays text/images and returns valid PDF bytes."""
    import pymupdf as fitz

    fake_pdf = fitz.open()
    fake_pdf.new_page()
    import io

    buf = io.BytesIO()
    fake_pdf.save(buf)
    pdf_bytes = buf.getvalue()

    import base64

    # Minimal valid 1×1 PNG (all image operations need a real PNG header + IHDR)
    fake_sig_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
        "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )

    with (
        patch(
            "rs_shared.services.utils.contract_pdf._fetch_asset",
            new_callable=AsyncMock,
            side_effect=[pdf_bytes, fake_sig_png],
        ),
    ):
        from rs_shared.services.utils.contract_pdf import generate_signed_contract

        result = await generate_signed_contract(
            company_name="חברת בדיקה",
            company_id="123456789",
            address="רח׳ הדוגמה 1, תל אביב",
            signed_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            company_signature_png_bytes=fake_sig_png,
        )

    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"
