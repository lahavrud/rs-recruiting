"""Sentry tunnel — forwards browser error envelopes to Sentry's ingest API.

The browser Sentry SDK sends envelopes to *.ingest.sentry.io directly, which
ad-blockers and strict CSPs routinely block (status: null CORS failure).
This endpoint acts as a same-origin relay so envelopes reach Sentry even when
the browser can't make the cross-origin request itself.

Delivery is **fire-and-forget**: the handler validates the envelope, schedules
the forward to Sentry as a background task, and immediately returns 202. Two
consequences, both deliberate:

- The browser is never blocked on Sentry's latency. Previously the tunnel
  awaited the full round-trip to ingest, so a slow Sentry became the browser's
  slowness (up to the 8s timeout).
- A slow or unreachable Sentry can never surface as a 5xx from this handler.
  That matters because the backend Sentry SDK reports 5xx responses
  (Starlette integration ``failed_request_status_codes``), so *raising* on an
  upstream failure would report "Sentry is unreachable" back *to Sentry* —
  amplifying load during the very outage it is trying to survive (a feedback
  loop). See issue #1005.

Security:
- Validates that the envelope's DSN matches FRONTEND_SENTRY_DSN (prevents
  using this endpoint as an open proxy for arbitrary Sentry projects).
- Rate-limited to 60 req/min per IP to limit abuse surface.

Observability:
- Upstream failures are logged as warnings, out-of-band from Sentry, so a
  Sentry outage never suppresses its own failure signal. They are never
  forwarded to Sentry.

Trade-off: because we respond before the forward completes, the tunnel no
longer relays Sentry's rate-limit headers (``X-Sentry-Rate-Limits`` /
``Retry-After``) back to the browser SDK, so the SDK won't back off on our
behalf. Acceptable at current volume.
"""

import json
import logging
from urllib.parse import urlparse

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Request,
    Response,
    status,
)

from rs_api.infrastructure.limiter import limiter
from rs_shared.core.infrastructure.config import settings

router = APIRouter(tags=["monitoring"])

_logger = logging.getLogger(__name__)

_TUNNEL_RATE = "60/minute"
_SENTRY_TIMEOUT = 8.0  # seconds
_ENVELOPE_CONTENT_TYPE = "application/x-sentry-envelope"


def _extract_dsn(body: bytes) -> str | None:
    """Return the DSN from the envelope header line, or None on parse failure."""
    try:
        header_line = body.split(b"\n", 1)[0]
        header = json.loads(header_line)
        return header.get("dsn") or None
    except (ValueError, KeyError):
        return None


def _sentry_ingest_url(dsn: str) -> str | None:
    """Derive the Sentry ingest URL from a DSN, or None if the DSN is malformed."""
    try:
        parsed = urlparse(dsn)
        host = parsed.hostname or ""
        if not host.endswith(".sentry.io"):
            return None
        project_id = parsed.path.strip("/")
        if not project_id.isdigit():
            return None
        return f"https://{host}/api/{project_id}/envelope/"
    except Exception:
        return None


async def _forward_envelope(ingest_url: str, body: bytes) -> None:
    """POST an envelope to Sentry ingest. Best-effort — never raises.

    Runs as a background task after the 202 response is sent, so upstream
    latency never blocks the browser. Every failure is logged out-of-band and
    swallowed: a propagated exception (or 5xx) would be captured by the backend
    Sentry SDK, recreating the feedback loop this design exists to avoid.
    """
    try:
        async with httpx.AsyncClient(timeout=_SENTRY_TIMEOUT) as client:
            resp = await client.post(
                ingest_url,
                content=body,
                headers={"Content-Type": _ENVELOPE_CONTENT_TYPE},
            )
        if resp.status_code >= status.HTTP_400_BAD_REQUEST:
            _logger.warning("Sentry tunnel: ingest returned %s", resp.status_code)
    except httpx.RequestError as exc:
        _logger.warning("Sentry tunnel: upstream request failed: %s", exc)
    except Exception:
        # Defensive: a background task must never let an unexpected error
        # propagate, or Starlette hands it to the Sentry SDK for capture.
        _logger.exception("Sentry tunnel: unexpected error forwarding envelope")


@router.post("/api/sentry-tunnel", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(_TUNNEL_RATE)
async def sentry_tunnel(
    request: Request, background_tasks: BackgroundTasks
) -> Response:
    """Validate a Sentry envelope and schedule its relay to Sentry ingest.

    Returns 202 immediately; the forward happens in the background so the
    browser never waits on Sentry and an upstream failure can't become a 5xx
    that Sentry would capture (issue #1005).
    """
    if not settings.frontend_sentry_dsn:
        # Not yet configured — 404 "endpoint unavailable" (never 5xx, which
        # the backend Sentry SDK would capture).
        _logger.debug("Sentry tunnel: FRONTEND_SENTRY_DSN not configured")
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    body = await request.body()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    dsn = _extract_dsn(body)
    if not dsn or dsn != settings.frontend_sentry_dsn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_dsn",
        )

    ingest_url = _sentry_ingest_url(dsn)
    if not ingest_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="malformed_dsn",
        )

    background_tasks.add_task(_forward_envelope, ingest_url, body)
    return Response(status_code=status.HTTP_202_ACCEPTED)
