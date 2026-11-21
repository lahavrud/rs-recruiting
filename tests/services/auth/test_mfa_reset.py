"""Tests for the break-glass MFA reset (scripts/reset_mfa.py's service)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.models import (
    AuditLog,
    EmailOutbox,
    MfaChallenge,
    MfaRecoveryCode,
    RefreshToken,
    User,
    UserMfa,
)
from rs_shared.services.auth.mfa_reset import reset_user_mfa


async def test_reset_wipes_mfa_and_sessions_and_audits(
    session: AsyncSession, admin_user: User
):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            UserMfa(user_id=admin_user.id, secret_encrypted="ct", enabled_at=now),
            MfaRecoveryCode(user_id=admin_user.id, code_hash="a" * 64),
            MfaChallenge(
                token_hash="b" * 64,
                user_id=admin_user.id,
                expires_at=now + timedelta(minutes=5),
            ),
            RefreshToken(
                token_hash="c" * 64,
                user_id=admin_user.id,
                expires_at=now + timedelta(days=1),
            ),
        ]
    )
    await session.commit()

    async with transactional(session):
        assert await reset_user_mfa(session, " Admin@Test.com ", reason="lost phone")

    for model in (UserMfa, MfaRecoveryCode, MfaChallenge, RefreshToken):
        assert (await session.execute(select(model))).first() is None
    audit = (await session.execute(select(AuditLog))).scalar_one()
    assert audit.action == "mfa_reset_break_glass"
    assert audit.target_id == admin_user.id and audit.detail == "lost phone"
    email = (await session.execute(select(EmailOutbox))).scalar_one()
    assert email.to_addrs == [admin_user.email] and "אופס" in email.subject


async def test_reset_unknown_email_changes_nothing(session: AsyncSession):
    assert not await reset_user_mfa(session, "nobody@example.com", reason="x")
    assert (await session.execute(select(AuditLog))).first() is None
    assert (await session.execute(select(EmailOutbox))).first() is None
