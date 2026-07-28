"""Email quota tracking and alerting.

Maintains a daily counter in the ``email_quota`` table. ``increment_and_alert``
is called by ``email_outbox.mark_sent`` — i.e. in the same transaction that
records a successful send, deliberately: when the bump had a transaction of its
own, a failed quota write raised *after* the email was already out, SQS
redelivered, and the recipient got it twice.

No hard enforcement is applied here — the provider's own 429 response is the
backstop. The goal is to surface usage before the ceiling is hit. Because the
counter shares the send's transaction, a bookkeeping failure under-counts rather
than resends; the count is advisory, so that is the cheaper side to err on.
"""

import logging
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.config import settings

logger = logging.getLogger(__name__)

_THRESHOLDS = (0.5, 0.75, 0.9, 1.0)


async def increment_and_alert(session: AsyncSession) -> None:
    """Increment today's send counter and log warnings at quota thresholds."""
    today = date.today()

    await session.execute(
        text(
            "INSERT INTO email_quota (date, count) VALUES (:d, 1) "
            "ON CONFLICT (date) DO UPDATE SET count = email_quota.count + 1"
        ),
        {"d": today},
    )

    daily_count: int = (
        await session.execute(
            text("SELECT count FROM email_quota WHERE date = :d"),
            {"d": today},
        )
    ).scalar_one()

    first_of_month = today.replace(day=1)
    monthly_count: int = (
        await session.execute(
            text("SELECT COALESCE(SUM(count), 0) FROM email_quota WHERE date >= :m"),
            {"m": first_of_month},
        )
    ).scalar_one()

    _check(daily_count, settings.email_daily_limit, "daily")
    _check(monthly_count, settings.email_monthly_limit, "monthly")


def _check(count: int, limit: int, label: str) -> None:
    ratio = count / limit if limit else 0
    for threshold in reversed(_THRESHOLDS):
        if ratio >= threshold:
            pct = int(threshold * 100)
            extra = {"count": count, "limit": limit, "label": label}
            if threshold >= 1.0:
                logger.critical("email_quota_exceeded", extra=extra)
            elif threshold >= 0.9:
                logger.critical("email_quota_%d_pct" % pct, extra=extra)
            else:
                logger.warning("email_quota_%d_pct" % pct, extra=extra)
            return
