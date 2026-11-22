"""Tests for the MFA security emails."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.models import EmailOutbox
from rs_shared.services.auth._mfa_notify import MfaEvent, notify_mfa_event


@pytest.mark.parametrize("event", list(MfaEvent))
async def test_every_event_queues_one_hebrew_email(
    session: AsyncSession, event: MfaEvent
):
    async with transactional(session):
        await notify_mfa_event(
            session, "owner@example.com", event, ip="203.0.113.1", remaining=4
        )

    row = (await session.execute(select(EmailOutbox))).scalar_one()
    assert row.to_addrs == ["owner@example.com"]
    assert row.subject.endswith("— RS Recruiting")
    assert "203.0.113.1" in row.body and "שעון ישראל" in row.body
    assert row.html_body is not None and 'dir="rtl"' in row.html_body
    assert "{remaining}" not in row.body


async def test_recovery_code_email_states_the_codes_left(session: AsyncSession):
    async with transactional(session):
        await notify_mfa_event(
            session, "o@example.com", MfaEvent.RECOVERY_CODE_USED, remaining=2
        )
    body = (await session.execute(select(EmailOutbox.body))).scalar_one()  # pyright: ignore[reportArgumentType]
    assert "נותרו 2 קודים" in body
