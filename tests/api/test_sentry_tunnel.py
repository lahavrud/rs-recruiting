"""Tests for the Sentry tunnel relay endpoint."""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import AsyncClient

from rs_shared.core.infrastructure.config import settings

VALID_DSN = "https://abc123@o12345.ingest.sentry.io/4567890"
INGEST_URL = "https://o12345.ingest.sentry.io/api/4567890/envelope/"


def _envelope(dsn: str | None) -> bytes:
    header: dict = {"event_id": "deadbeef" * 4, "sent_at": "2026-01-01T00:00:00Z"}
    if dsn is not None:
        header["dsn"] = dsn
    return json.dumps(header).encode() + b'\n{"type":"event","length":2}\n{}\n'


def _mock_async_client(*, post: AsyncMock) -> AsyncMock:
    """Build an AsyncMock standing in for httpx.AsyncClient() as a context manager."""
    client = AsyncMock()
    client.post = post
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    return client


@pytest.fixture
def _configure_dsn(monkeypatch):
    monkeypatch.setattr(settings, "frontend_sentry_dsn", VALID_DSN)


@pytest.mark.asyncio
async def test_returns_404_when_dsn_not_configured(public_client: AsyncClient):
    """If the server has no DSN configured the tunnel returns 404.

    404 (not 5xx) so the backend Sentry SDK doesn't capture it and create
    a feedback loop where the tunnel's own failure gets reported to Sentry.
    """
    # Default settings have empty frontend_sentry_dsn (see config defaults).
    resp = await public_client.post("/api/sentry-tunnel", content=_envelope(VALID_DSN))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rejects_empty_body(public_client: AsyncClient, _configure_dsn):
    resp = await public_client.post("/api/sentry-tunnel", content=b"")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rejects_mismatched_dsn(public_client: AsyncClient, _configure_dsn):
    """Envelopes pointing at a different Sentry project must be refused."""
    other = "https://xyz@o99999.ingest.sentry.io/1111111"
    resp = await public_client.post("/api/sentry-tunnel", content=_envelope(other))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rejects_missing_dsn_in_envelope(
    public_client: AsyncClient, _configure_dsn
):
    resp = await public_client.post("/api/sentry-tunnel", content=_envelope(None))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rejects_unparseable_header(public_client: AsyncClient, _configure_dsn):
    resp = await public_client.post("/api/sentry-tunnel", content=b"not-json\n{}\n{}\n")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rejects_dsn_with_non_sentry_host(
    public_client: AsyncClient, monkeypatch
):
    """Hosts outside *.sentry.io are refused even if configured (defense in depth)."""
    bad = "https://abc@evil.example.com/123"
    monkeypatch.setattr(settings, "frontend_sentry_dsn", bad)
    resp = await public_client.post("/api/sentry-tunnel", content=_envelope(bad))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rejects_dsn_with_non_numeric_project(
    public_client: AsyncClient, monkeypatch
):
    bad = "https://abc@o1.ingest.sentry.io/not-a-number"
    monkeypatch.setattr(settings, "frontend_sentry_dsn", bad)
    resp = await public_client.post("/api/sentry-tunnel", content=_envelope(bad))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_accepts_and_forwards_envelope(
    public_client: AsyncClient, _configure_dsn
):
    """Happy path: returns 202 and the background task POSTs to the ingest URL.

    Starlette runs background tasks within the ASGI call, so the forward has
    completed by the time the client request returns.
    """
    body = _envelope(VALID_DSN)

    upstream_response = MagicMock()
    upstream_response.status_code = 200

    post = AsyncMock(return_value=upstream_response)
    with patch(
        "rs_api.api.sentry_tunnel.httpx.AsyncClient",
        return_value=_mock_async_client(post=post),
    ):
        resp = await public_client.post("/api/sentry-tunnel", content=body)

    # Browser is unblocked immediately, independent of Sentry's response.
    assert resp.status_code == 202
    assert resp.content == b""

    post.assert_awaited_once()
    args, kwargs = post.call_args
    assert args[0] == INGEST_URL
    assert kwargs["content"] == body
    assert kwargs["headers"]["Content-Type"] == "application/x-sentry-envelope"


@pytest.mark.asyncio
async def test_upstream_timeout_does_not_error(
    public_client: AsyncClient, _configure_dsn, caplog
):
    """Regression (#1005): an upstream ReadTimeout must NOT become a 5xx.

    Raising a 5xx here gets captured by the backend Sentry SDK, creating a
    feedback loop during a Sentry outage. The failure is swallowed in the
    background task and only logged out-of-band.
    """
    post = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
    with (
        patch(
            "rs_api.api.sentry_tunnel.httpx.AsyncClient",
            return_value=_mock_async_client(post=post),
        ),
        caplog.at_level(logging.WARNING, logger="rs_api.api.sentry_tunnel"),
    ):
        resp = await public_client.post(
            "/api/sentry-tunnel", content=_envelope(VALID_DSN)
        )

    assert resp.status_code == 202
    post.assert_awaited_once()
    assert any("upstream request failed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_upstream_error_status_is_logged_not_relayed(
    public_client: AsyncClient, _configure_dsn, caplog
):
    """A non-2xx from Sentry (e.g. 429) is logged but not relayed to the browser.

    The browser already received 202; fire-and-forget means we no longer pass
    Sentry's status/headers back (documented trade-off).
    """
    upstream_response = MagicMock()
    upstream_response.status_code = 429

    post = AsyncMock(return_value=upstream_response)
    with (
        patch(
            "rs_api.api.sentry_tunnel.httpx.AsyncClient",
            return_value=_mock_async_client(post=post),
        ),
        caplog.at_level(logging.WARNING, logger="rs_api.api.sentry_tunnel"),
    ):
        resp = await public_client.post(
            "/api/sentry-tunnel", content=_envelope(VALID_DSN)
        )

    assert resp.status_code == 202
    assert any("ingest returned 429" in r.message for r in caplog.records)
