"""FastAPI middleware: request correlation IDs and APM latency logging.

The framework-free logging primitives (`request_id_var`, `RequestIdFilter`)
live in `request_context.py` so the worker can use them without Starlette;
they're re-exported here for backward compatibility with existing imports.
"""

import logging
import secrets as _secrets
import time
import uuid
from collections.abc import Awaitable, Callable

import sentry_sdk
from opentelemetry import trace as otel_trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from rs_shared.core.infrastructure.request_context import (
    RequestIdFilter,
    request_id_var,
)

__all__ = [
    "OriginVerifyMiddleware",
    "RequestIdFilter",
    "RequestMiddleware",
    "request_id_var",
]

logger = logging.getLogger(__name__)

_HEALTH_PATH = "/health"


class RequestMiddleware(BaseHTTPMiddleware):
    """Per-request correlation ID + APM latency in a single middleware pass.

    Generates a UUID per request, stores it in a ContextVar so every log line
    in the request carries the same request_id, and returns it as X-Request-ID.

    Logs method/path/status_code/duration_ms on every response (including
    errors — the finally block fires even when call_next raises) for p95/p99
    latency analysis in Grafana (logs ship via OTLP → Loki).

    /health is excluded from APM logging (Route 53 polls it every 30 s).
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = str(uuid.uuid4())
        request_id_var.set(rid)
        span = otel_trace.get_current_span()
        span_context = span.get_span_context()
        if span_context.is_valid:
            span.set_attribute("app.request_id", rid)
            sentry_sdk.set_tag("trace_id", format(span_context.trace_id, "032x"))

        path = request.url.path
        t0 = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            if path != _HEALTH_PATH:
                duration_ms = round((time.perf_counter() - t0) * 1000)
                logger.info(
                    "request",
                    extra={
                        "request_id": rid,
                        "method": request.method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    },
                )


class OriginVerifyMiddleware(BaseHTTPMiddleware):
    """Reject requests that didn't come through CloudFront.

    The ALB origin was locked to CloudFront's origin-facing prefix list at the
    security-group level; an API Gateway origin has no equivalent lock
    (execute-api is publicly routable). Parity comes from a shared secret:
    CloudFront stamps ``x-origin-verify`` on every origin request (a custom
    origin header, re-stamped by the bot-prerender Lambda@Edge which replaces
    the origin config), and this middleware 403s anything without it.

    Enforcement is opt-in: ``secret=None`` (local dev, worker, tests without
    the env) disables it entirely. ``/health`` is always exempt — the ALB
    health checker probes the target directly, not through CloudFront, and a
    403 there would fail the target group and take the service out.

    Registered outermost (after CORS in code order): rejected probes never
    reach the APM middleware, so they don't pollute request logs beyond the
    warning emitted here.
    """

    def __init__(self, app, secret: str | None = None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._secret = secret

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if self._secret is None or request.url.path == _HEALTH_PATH:
            return await call_next(request)

        provided = request.headers.get("x-origin-verify", "")
        if not _secrets.compare_digest(provided, self._secret):
            # Path only — never log the provided header value.
            logger.warning(
                "origin_verify_failed",
                extra={"path": request.url.path, "method": request.method},
            )
            return JSONResponse(status_code=403, content={"detail": "forbidden"})

        return await call_next(request)
