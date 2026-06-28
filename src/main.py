import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi import routing as fastapi_routing
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from pythonjsonlogger import json as jsonlogger
from slowapi.errors import RateLimitExceeded

from src.api import analytics, sentry_tunnel, seo
from src.api.admin import (
    applications as admin_applications,
)
from src.api.admin import (
    audit as admin_audit,
)
from src.api.admin import (
    candidates as admin_candidates,
)
from src.api.admin import (
    companies as admin_companies,
)
from src.api.admin import (
    invites as admin_invites,
)
from src.api.admin import (
    jobs as admin_jobs,
)
from src.api.admin import (
    matches as admin_matches,
)
from src.api.admin import (
    overview as admin_overview,
)
from src.api.auth import (
    activation,
    candidate_registration,
    invites,
    password_change,
    password_reset,
    registration,
)
from src.api.auth import (
    login as auth,
)
from src.api.auth import sessions as auth_sessions
from src.api.candidate import applications as candidate_applications
from src.api.candidate import data_export as candidate_data_export
from src.api.candidate import profile as candidate_profile
from src.api.company import jobs as company_jobs
from src.api.company import profile as companies
from src.api.company import resumes
from src.api.public import applications as candidates
from src.api.public import jobs as public
from src.core.infrastructure.config import settings, validate_settings
from src.core.infrastructure.database import engine, init_db
from src.core.infrastructure.dependencies import client_ip
from src.core.infrastructure.middleware import RequestIdFilter, RequestMiddleware
from src.core.infrastructure.telemetry import configure_telemetry, shutdown_telemetry

if settings.sentry_dsn:
    try:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            release=os.environ.get("SENTRY_RELEASE"),
            traces_sample_rate=0.0,
            send_default_pii=False,
        )
    except Exception as _sentry_err:
        # A misconfigured DSN must never crash the server.
        import logging as _logging

        _logging.getLogger(__name__).error(
            "Sentry init failed (check SENTRY_DSN in SSM): %s", _sentry_err
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    validate_settings()
    await init_db()
    yield
    shutdown_telemetry()


def _configure_logging() -> None:
    """Set up JSON structured logging on the root logger.

    In production, every log line is a JSON object so CloudWatch Logs Insights
    can parse fields natively (filter level="ERROR", stats by endpoint, etc.).
    In development the same JSON format is used for consistency; pipe through
    `jq` locally if you prefer pretty output.
    """
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(request_id)s"
        " %(otelTraceID)s %(otelSpanID)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    # Filter on the handler (not the logger) so it runs for propagated messages
    # from child loggers — logger-level filters are skipped during propagation.
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())


_configure_logging()

# Must run after _configure_logging() — LoggingInstrumentor adds a handler to
# the root logger that bridges stdlib logging to the OTLP log exporter, and
# _configure_logging() replaces root.handlers wholesale.
configure_telemetry("rs-recruiting-api")

logger = logging.getLogger(__name__)


# FastAPI 0.137+ stores include_router entries as internal _IncludedRouter
# objects without a .path attribute. opentelemetry-instrumentation-fastapi
# expects .path during partial route matches, which raises AttributeError in
# tests and request handling. Provide a compatibility .path shim until the
# instrumentation package supports this FastAPI router shape natively.
_included_router = getattr(fastapi_routing, "_IncludedRouter", None)


def _included_router_path(router: object) -> str:
    include_context = getattr(router, "include_context", None)
    try:
        prefix = getattr(include_context, "prefix", "")
    except AttributeError:
        return ""
    return prefix or ""


if _included_router is not None and not hasattr(_included_router, "path"):
    _included_router.path = property(_included_router_path)  # type: ignore[attr-defined]  # monkeypatching a property onto FastAPI's APIRoute class; stubs don't model this


class _HealthCheckLogFilter(logging.Filter):
    # Route 53 polls /health every 30s, which would otherwise add ~2.8k
    # GET /health 200 lines/day to CloudWatch — pure noise that crowds out
    # real signal during incident triage.
    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(_HealthCheckLogFilter())
logging.getLogger().addFilter(RequestIdFilter())


app = FastAPI(title="RS Recruitment API", lifespan=lifespan)
app.add_middleware(RequestMiddleware)
FastAPIInstrumentor().instrument_app(app)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    logger.warning(
        "rate_limit_hit", extra={"path": request.url.path, "ip": client_ip(request)}
    )
    return JSONResponse(status_code=429, content={"detail": "too_many_requests"})


# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include routers
app.include_router(auth.router)
app.include_router(auth_sessions.router)
app.include_router(registration.router)
app.include_router(candidate_registration.router)
app.include_router(activation.router)
app.include_router(password_reset.router)
app.include_router(password_change.router)
app.include_router(invites.router)
app.include_router(admin_companies.router)
app.include_router(admin_invites.router)
app.include_router(admin_jobs.router)
app.include_router(admin_overview.router)
app.include_router(admin_matches.router)
app.include_router(admin_applications.router)
app.include_router(admin_audit.router)
app.include_router(admin_candidates.router)
app.include_router(companies.router)
app.include_router(company_jobs.router)
app.include_router(candidate_profile.router)
app.include_router(candidate_data_export.router)
app.include_router(candidate_applications.router)
app.include_router(public.router)
app.include_router(candidates.router)
app.include_router(candidates.jobs_apply_router)
app.include_router(resumes.router)
app.include_router(sentry_tunnel.router)
app.include_router(analytics.router)
app.include_router(seo.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
    }
