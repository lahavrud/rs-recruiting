"""Tests for the GA4 analytics tunnel endpoint."""

import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient

from src.core.infrastructure.config import settings


@pytest.fixture
def _configure_ga4(monkeypatch):
    monkeypatch.setattr(settings, "ga4_measurement_id", "G-TEST12345")
    monkeypatch.setattr(
        settings, "ga4_api_secret", "test-secret"
    )  # pragma: allowlist secret


def _payload(
    name: str = "apply_submit",
    params: dict | None = None,
    client_id: str = "123.456",
) -> dict:
    return {"name": name, "params": params or {"job_id": 1}, "client_id": client_id}


@pytest.mark.asyncio
async def test_returns_404_when_not_configured(public_client: AsyncClient):
    """Endpoint returns 404 when GA4 credentials are not set."""
    resp = await public_client.post("/api/analytics/collect", json=_payload())
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_returns_404_when_only_measurement_id_set(
    public_client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(settings, "ga4_measurement_id", "G-TEST12345")
    resp = await public_client.post("/api/analytics/collect", json=_payload())
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rejects_invalid_event_name(public_client: AsyncClient, _configure_ga4):
    resp = await public_client.post(
        "/api/analytics/collect", json=_payload(name="invalid name!")
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rejects_event_name_starting_with_digit(
    public_client: AsyncClient, _configure_ga4
):
    resp = await public_client.post(
        "/api/analytics/collect", json=_payload(name="1bad_name")
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rejects_empty_client_id(public_client: AsyncClient, _configure_ga4):
    resp = await public_client.post(
        "/api/analytics/collect", json=_payload(client_id="")
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_forwards_event_to_ga4(public_client: AsyncClient, _configure_ga4):
    """Happy path: event is POSTed to GA4 Measurement Protocol, returns 204."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=AsyncMock(status_code=204))
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("src.api.analytics.httpx.AsyncClient", return_value=mock_client):
        resp = await public_client.post(
            "/api/analytics/collect",
            json=_payload(
                name="apply_submit", params={"job_id": 42}, client_id="111.222"
            ),
        )

    assert resp.status_code == 204

    mock_client.post.assert_awaited_once()
    _, kwargs = mock_client.post.call_args
    assert kwargs["params"]["measurement_id"] == "G-TEST12345"
    assert kwargs["json"]["client_id"] == "111.222"
    assert kwargs["json"]["events"][0]["name"] == "apply_submit"
    assert kwargs["json"]["events"][0]["params"]["job_id"] == 42


@pytest.mark.asyncio
async def test_returns_204_when_upstream_fails(
    public_client: AsyncClient, _configure_ga4, caplog
):
    """Upstream GA4 failure must not propagate — always return 204 to browser."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("src.api.analytics.httpx.AsyncClient", return_value=mock_client):
        with caplog.at_level(logging.WARNING):
            resp = await public_client.post("/api/analytics/collect", json=_payload())

    assert resp.status_code == 204
    mock_client.post.assert_awaited_once()
    assert any("upstream request failed" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_accepts_valid_event_names(public_client: AsyncClient, _configure_ga4):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=AsyncMock(status_code=204))
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    names = ("job_view", "apply_start", "apply_submit", "a", "A1_b2")
    with patch("src.api.analytics.httpx.AsyncClient", return_value=mock_client):
        for name in names:
            resp = await public_client.post(
                "/api/analytics/collect", json=_payload(name=name)
            )
            assert resp.status_code == 204, f"Expected 204 for event name {name!r}"

    assert mock_client.post.call_count == len(names)
    for name, call in zip(names, mock_client.post.call_args_list, strict=True):
        _, kwargs = call
        assert kwargs["json"]["events"][0]["name"] == name
        assert kwargs["params"]["measurement_id"] == "G-TEST12345"
