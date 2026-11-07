"""Dependency checks behind the public ``/health`` endpoint.

``/health`` is what the ECS container health check, the Route 53 health check
and the deploy smoke check all poll, so it must fail when the API cannot do
its job — not only when the process is down. It checks every dependency a
request needs: Postgres, object storage, and the task queue.

The endpoint is public, so the result exposes only a fixed ``ok`` / ``fail``
per check: never error text, hostnames, bucket or queue names, or timings.
Failure details go to the server log instead.

Results are cached for ``_CACHE_SECONDS`` and concurrent callers share one
in-flight run, so polling (or abusing) the endpoint cannot multiply load on
the dependencies it checks.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Literal

import aioboto3
from sqlalchemy import text

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.infrastructure.database import engine
from rs_shared.core.services.storage import get_storage_provider

logger = logging.getLogger(__name__)

CheckResult = Literal["ok", "fail", "skipped"]

_CHECK_TIMEOUT_SECONDS = 3.0
_CACHE_SECONDS = 10.0

_cache: tuple[float, dict[str, CheckResult]] | None = None
_lock = asyncio.Lock()


async def check_database() -> CheckResult:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return "ok"


async def check_storage() -> CheckResult:
    await get_storage_provider().check_health()
    return "ok"


async def check_queue() -> CheckResult:
    # No queue configured means tasks run inline (local dev): nothing to reach.
    if not settings.sqs_queue_url:
        return "skipped"
    session = aioboto3.Session()
    async with session.client(  # type: ignore[attr-defined]  # aioboto3 session.client() is untyped; stubs incomplete
        "sqs",
        region_name=settings.aws_region,
        endpoint_url=settings.sqs_endpoint_url,
    ) as sqs:
        await sqs.get_queue_attributes(
            QueueUrl=settings.sqs_queue_url, AttributeNames=["QueueArn"]
        )
    return "ok"


CHECKS: dict[str, Callable[[], Awaitable[CheckResult]]] = {
    "database": check_database,
    "storage": check_storage,
    "queue": check_queue,
}


async def _run_one(
    name: str, check: Callable[[], Awaitable[CheckResult]]
) -> CheckResult:
    try:
        return await asyncio.wait_for(check(), timeout=_CHECK_TIMEOUT_SECONDS)
    except Exception:
        # Server-side only: the public response never carries this detail.
        logger.warning("health_check_failed", extra={"check": name}, exc_info=True)
        return "fail"


async def run_health_checks() -> dict[str, CheckResult]:
    """Run every check concurrently, or return the cached result if fresh."""
    global _cache
    async with _lock:
        now = time.monotonic()
        if _cache is not None and now - _cache[0] < _CACHE_SECONDS:
            return _cache[1]
        names = list(CHECKS)
        results = await asyncio.gather(*(_run_one(n, CHECKS[n]) for n in names))
        checks = dict(zip(names, results))
        _cache = (time.monotonic(), checks)
        return checks


def reset_cache() -> None:
    """Forget the cached result (tests, and anything that must re-probe now)."""
    global _cache
    _cache = None
