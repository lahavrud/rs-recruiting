"""Tests for the daily/monthly email quota counter and its threshold alerts."""

import logging
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.services import email_quota
from rs_shared.core.services.email_quota import _check, increment_and_alert
from rs_shared.models import EmailQuota

_TODAY = date(2026, 3, 15)
_LOGGER = "rs_shared.core.services.email_quota"


class _FixedDate(date):
    """`date` whose today() is pinned, so month boundaries are deterministic."""

    @classmethod
    def today(cls) -> date:
        return _TODAY


@pytest.fixture
def fixed_today():
    with patch.object(email_quota, "date", _FixedDate):
        yield


@pytest.fixture
def high_limits(monkeypatch):
    """Limits far above any test count, so no threshold logs by accident."""
    monkeypatch.setattr(settings, "email_daily_limit", 10_000)
    monkeypatch.setattr(settings, "email_monthly_limit", 10_000)


async def _count_on(session: AsyncSession, day: date) -> int | None:
    row = await session.get(EmailQuota, day)
    return None if row is None else row.count


@pytest.mark.asyncio
async def test_first_send_of_the_day_creates_the_row(
    session: AsyncSession, fixed_today, high_limits
):
    await increment_and_alert(session)

    assert await _count_on(session, _TODAY) == 1


@pytest.mark.asyncio
async def test_later_sends_increment_the_same_row(
    session: AsyncSession, fixed_today, high_limits
):
    for _ in range(3):
        await increment_and_alert(session)

    assert await _count_on(session, _TODAY) == 3


@pytest.mark.asyncio
async def test_monthly_total_counts_this_month_only(
    session: AsyncSession, fixed_today, monkeypatch, caplog
):
    """Earlier days this month count toward the monthly limit; last month's don't."""
    session.add(EmailQuota(day=date(2026, 3, 1), count=40))
    session.add(EmailQuota(day=date(2026, 2, 28), count=1_000))
    await session.flush()
    monkeypatch.setattr(settings, "email_daily_limit", 10_000)
    monkeypatch.setattr(settings, "email_monthly_limit", 82)  # 41 / 82 = 50%

    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        await increment_and_alert(session)

    [record] = caplog.records
    assert record.getMessage() == "email_quota_50_pct"
    assert record.label == "monthly"
    assert record.count == 41  # 40 earlier this month + today's 1, not February's


@pytest.mark.parametrize(
    ("count", "expected_message", "expected_level"),
    [
        (49, None, None),
        (50, "email_quota_50_pct", logging.WARNING),
        (75, "email_quota_75_pct", logging.WARNING),
        (89, "email_quota_75_pct", logging.WARNING),
        (90, "email_quota_90_pct", logging.CRITICAL),
        (100, "email_quota_exceeded", logging.CRITICAL),
        (250, "email_quota_exceeded", logging.CRITICAL),
    ],
)
def test_check_logs_only_the_highest_threshold_crossed(
    caplog, count, expected_message, expected_level
):
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        _check(count, 100, "daily")

    if expected_message is None:
        assert caplog.records == []
        return
    [record] = caplog.records
    assert record.getMessage() == expected_message
    assert record.levelno == expected_level
    assert (record.count, record.limit, record.label) == (count, 100, "daily")


def test_check_with_no_limit_configured_never_alerts(caplog):
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        _check(1_000_000, 0, "daily")

    assert caplog.records == []
