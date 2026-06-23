import logging

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import _HealthCheckLogFilter, app


@pytest.mark.asyncio
async def test_health_endpoint_returns_200_with_json_status():
    """Test that the /health endpoint returns status 200 and correct JSON."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": "development",
    }


def _make_record(message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_health_filter_drops_health_access_lines():
    f = _HealthCheckLogFilter()
    assert f.filter(_make_record('127.0.0.1 - "GET /health HTTP/1.1" 200')) is False


def test_health_filter_keeps_api_requests():
    f = _HealthCheckLogFilter()
    assert f.filter(_make_record('127.0.0.1 - "GET /api/jobs HTTP/1.1" 200')) is True


def test_health_filter_keeps_auth_requests():
    f = _HealthCheckLogFilter()
    assert (
        f.filter(_make_record('127.0.0.1 - "POST /api/auth/login HTTP/1.1" 401'))
        is True
    )


def test_health_filter_attached_to_uvicorn_access_logger():
    logger = logging.getLogger("uvicorn.access")
    assert any(isinstance(f, _HealthCheckLogFilter) for f in logger.filters)
