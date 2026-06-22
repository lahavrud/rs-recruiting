"""FastAPI middleware: request correlation IDs and APM latency logging."""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

import sentry_sdk
from opentelemetry import trace as otel_trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

logger = logging.getLogger(__name__)

_HEALTH_PATH = "/health"


class RequestIdFilter(logging.Filter):
    """Inject the current request_id into every LogRecord emitted in this context.

    Install once on the root logger so every logger in the process picks it up.
    When called outside a request context the field is an empty string.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("")  # type: ignore[attr-defined]  # dynamically attaching request_id to LogRecord; stdlib stubs don't declare it
        return True


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
