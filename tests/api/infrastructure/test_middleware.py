"""Tests for RequestMiddleware (the Starlette request-correlation middleware)."""

import logging

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from rs_api.infrastructure.middleware import (
    OriginVerifyMiddleware,
    RequestMiddleware,
    SecurityHeadersMiddleware,
    request_id_var,
)


def _make_app(handler=None):
    """Minimal Starlette app with RequestMiddleware for testing."""

    async def _default(request: Request) -> Response:
        return JSONResponse({"path": request.url.path})

    async def _error(request: Request) -> Response:
        raise RuntimeError("boom")

    routes = [
        Route("/ok", _default),
        Route("/health", _default),
        Route("/error", _error),
    ]
    if handler:
        routes.insert(0, Route("/custom", handler))

    app = Starlette(routes=routes)
    app.add_middleware(RequestMiddleware)
    return app


@pytest.mark.asyncio
async def test_request_id_header_present():
    """Every response carries X-Request-ID."""
    async with AsyncClient(
        transport=ASGITransport(app=_make_app()), base_url="http://test"
    ) as client:
        response = await client.get("/ok")
    assert "x-request-id" in response.headers
    rid = response.headers["x-request-id"]
    assert len(rid) == 36  # UUID4 format


@pytest.mark.asyncio
async def test_request_id_unique_per_request():
    """Each request gets a distinct UUID."""
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r1 = await client.get("/ok")
        r2 = await client.get("/ok")
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


@pytest.mark.asyncio
async def test_request_id_var_set_during_request(caplog):
    """request_id_var is populated while the handler runs."""
    captured_id: list[str] = []

    async def _capture(request: Request) -> Response:
        captured_id.append(request_id_var.get(""))
        return JSONResponse({})

    async with AsyncClient(
        transport=ASGITransport(app=_make_app(_capture)), base_url="http://test"
    ) as client:
        response = await client.get("/custom")

    assert len(captured_id) == 1
    assert captured_id[0] == response.headers["x-request-id"]


@pytest.mark.asyncio
async def test_apm_log_emitted(caplog):
    """A 'request' log entry with path/status_code/duration_ms is emitted."""
    with caplog.at_level(logging.INFO, logger="rs_api.infrastructure.middleware"):
        async with AsyncClient(
            transport=ASGITransport(app=_make_app()), base_url="http://test"
        ) as client:
            await client.get("/ok")

    records = [r for r in caplog.records if r.getMessage() == "request"]
    assert len(records) == 1
    rec = records[0]
    assert rec.__dict__["path"] == "/ok"
    assert rec.__dict__["status_code"] == 200
    assert isinstance(rec.__dict__["duration_ms"], int)


@pytest.mark.asyncio
async def test_health_not_logged(caplog):
    """/health requests are excluded from APM logging."""
    with caplog.at_level(logging.INFO, logger="rs_api.infrastructure.middleware"):
        async with AsyncClient(
            transport=ASGITransport(app=_make_app()), base_url="http://test"
        ) as client:
            await client.get("/health")

    records = [r for r in caplog.records if r.getMessage() == "request"]
    assert len(records) == 0


@pytest.mark.asyncio
async def test_error_still_logs_with_500(caplog):
    """When call_next raises, the APM log fires with status_code=500."""
    with caplog.at_level(logging.INFO, logger="rs_api.infrastructure.middleware"):
        async with AsyncClient(
            transport=ASGITransport(app=_make_app()), base_url="http://test"
        ) as client:
            try:
                await client.get("/error")
            except Exception:
                pass

    records = [r for r in caplog.records if r.getMessage() == "request"]
    assert len(records) == 1
    assert records[0].__dict__["status_code"] == 500


# --- OriginVerifyMiddleware (CloudFront origin verification) ---


def _make_verify_app(secret):
    """Minimal Starlette app with OriginVerifyMiddleware for testing."""

    async def _default(request: Request) -> Response:
        return JSONResponse({"path": request.url.path})

    app = Starlette(routes=[Route("/ok", _default), Route("/health", _default)])
    app.add_middleware(OriginVerifyMiddleware, secret=secret)
    return app


@pytest.mark.asyncio
async def test_origin_verify_disabled_without_secret():
    """secret=None disables enforcement entirely (local dev / worker)."""
    async with AsyncClient(
        transport=ASGITransport(app=_make_verify_app(None)), base_url="http://test"
    ) as client:
        response = await client.get("/ok")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_origin_verify_rejects_missing_header():
    async with AsyncClient(
        transport=ASGITransport(app=_make_verify_app("s3cret")), base_url="http://test"
    ) as client:
        response = await client.get("/ok")
    assert response.status_code == 403
    assert response.json() == {"detail": "forbidden"}


@pytest.mark.asyncio
async def test_origin_verify_rejects_wrong_header():
    async with AsyncClient(
        transport=ASGITransport(app=_make_verify_app("s3cret")), base_url="http://test"
    ) as client:
        response = await client.get("/ok", headers={"x-origin-verify": "wrong"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_origin_verify_accepts_matching_header():
    async with AsyncClient(
        transport=ASGITransport(app=_make_verify_app("s3cret")), base_url="http://test"
    ) as client:
        response = await client.get("/ok", headers={"x-origin-verify": "s3cret"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_origin_verify_health_always_exempt():
    """/health must pass without the header — the ALB health checker probes the
    target directly (not through CloudFront); a 403 would fail the target group."""
    async with AsyncClient(
        transport=ASGITransport(app=_make_verify_app("s3cret")), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_origin_verify_failure_logs_path_not_secret(caplog):
    """Rejections log the path but never the provided header value."""
    with caplog.at_level(logging.WARNING, logger="rs_api.infrastructure.middleware"):
        async with AsyncClient(
            transport=ASGITransport(app=_make_verify_app("s3cret")),
            base_url="http://test",
        ) as client:
            await client.get("/ok", headers={"x-origin-verify": "sniffed-value"})

    records = [r for r in caplog.records if r.getMessage() == "origin_verify_failed"]
    assert len(records) == 1
    assert records[0].__dict__["path"] == "/ok"
    assert "sniffed-value" not in str(records[0].__dict__)


# --- SecurityHeadersMiddleware (defensive response headers) ---


def _make_security_app(*, hsts=False, extra_routes=None):
    """Minimal Starlette app with SecurityHeadersMiddleware for testing."""

    async def _default(request: Request) -> Response:
        return JSONResponse({"path": request.url.path})

    async def _html(request: Request) -> Response:
        return HTMLResponse("<!doctype html><title>hi</title>")

    routes = [Route("/ok", _default), Route("/html", _html)]
    for path, handler in (extra_routes or {}).items():
        routes.append(Route(path, handler))

    app = Starlette(routes=routes)
    app.add_middleware(SecurityHeadersMiddleware, hsts=hsts)
    return app


@pytest.mark.asyncio
async def test_security_headers_present():
    """Every response carries the static defensive headers + the strict CSP."""
    async with AsyncClient(
        transport=ASGITransport(app=_make_security_app()), base_url="http://test"
    ) as client:
        response = await client.get("/ok")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == (
        "geolocation=(), camera=(), microphone=()"
    )
    csp = response.headers["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


@pytest.mark.asyncio
async def test_hsts_omitted_when_disabled():
    """HSTS is absent unless explicitly enabled (plaintext dev http)."""
    async with AsyncClient(
        transport=ASGITransport(app=_make_security_app(hsts=False)),
        base_url="http://test",
    ) as client:
        response = await client.get("/ok")
    assert "strict-transport-security" not in response.headers


@pytest.mark.asyncio
async def test_hsts_present_when_enabled():
    """HSTS is emitted in deployed HTTPS environments."""
    async with AsyncClient(
        transport=ASGITransport(app=_make_security_app(hsts=True)),
        base_url="http://test",
    ) as client:
        response = await client.get("/ok")
    hsts = response.headers["strict-transport-security"]
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts


@pytest.mark.asyncio
async def test_csp_skipped_on_html_response():
    """The strict `default-src 'none'` CSP would blank any HTML the app serves
    (Swagger UI, `/api/og/*` prerender), so it's gated on a JSON content-type.
    The other defensive headers still apply to HTML responses."""
    async with AsyncClient(
        transport=ASGITransport(app=_make_security_app()), base_url="http://test"
    ) as client:
        response = await client.get("/html")
    assert "content-security-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
async def test_security_headers_do_not_clobber_handler_values():
    """setdefault semantics: a handler that sets its own header wins."""

    async def _custom_csp(request: Request) -> Response:
        resp = JSONResponse({})
        resp.headers["Content-Security-Policy"] = "default-src 'self'"
        return resp

    app = _make_security_app(extra_routes={"/custom": _custom_csp})
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/custom")
    assert response.headers["content-security-policy"] == "default-src 'self'"


@pytest.mark.asyncio
async def test_security_headers_wired_into_real_app(public_client):
    """Guards the main.py registration + ordering, not just an isolated app:
    the middleware must actually stamp a real response from rs_api.main.app."""
    response = await public_client.get("/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in response.headers["content-security-policy"]
