"""Dependency checks behind /health (core/infrastructure/health.py)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from rs_shared.core.infrastructure import health


def _counting_check(result: str = "ok"):
    calls = {"n": 0}

    async def check():
        calls["n"] += 1
        return result

    return check, calls


async def test_database_check_runs_a_real_query():
    assert await health.check_database() == "ok"


async def test_storage_check_passes_for_local_storage():
    assert await health.check_storage() == "ok"


async def test_queue_check_is_skipped_without_a_queue(monkeypatch):
    monkeypatch.setattr(health.settings, "sqs_queue_url", "")
    assert await health.check_queue() == "skipped"


async def test_queue_check_reads_the_configured_queue(monkeypatch):
    monkeypatch.setattr(health.settings, "sqs_queue_url", "https://sqs.test/q")
    sqs = AsyncMock()
    session = MagicMock()
    session.client.return_value.__aenter__.return_value = sqs
    monkeypatch.setattr(health.aioboto3, "Session", lambda: session)

    assert await health.check_queue() == "ok"
    sqs.get_queue_attributes.assert_awaited_once_with(
        QueueUrl="https://sqs.test/q", AttributeNames=["QueueArn"]
    )


async def test_failing_check_reports_fail_and_others_still_run(monkeypatch):
    async def boom():
        raise RuntimeError("secret detail")

    ok, _ = _counting_check()
    monkeypatch.setattr(health, "CHECKS", {"database": boom, "storage": ok})

    assert await health.run_health_checks() == {"database": "fail", "storage": "ok"}


async def test_hanging_check_times_out_as_fail(monkeypatch):
    async def hang():
        await asyncio.sleep(60)
        return "ok"

    monkeypatch.setattr(health, "_CHECK_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(health, "CHECKS", {"queue": hang})

    assert await health.run_health_checks() == {"queue": "fail"}


async def test_results_are_cached_between_calls(monkeypatch):
    check, calls = _counting_check()
    monkeypatch.setattr(health, "CHECKS", {"database": check})

    await health.run_health_checks()
    await health.run_health_checks()
    assert calls["n"] == 1

    monkeypatch.setattr(health, "_CACHE_SECONDS", 0.0)
    await health.run_health_checks()
    assert calls["n"] == 2


async def test_concurrent_callers_share_one_run(monkeypatch):
    calls = {"n": 0}

    async def slow():
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return "ok"

    monkeypatch.setattr(health, "CHECKS", {"database": slow})

    results = await asyncio.gather(*(health.run_health_checks() for _ in range(5)))
    assert all(r == {"database": "ok"} for r in results)
    assert calls["n"] == 1
