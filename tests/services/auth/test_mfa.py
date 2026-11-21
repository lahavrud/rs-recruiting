"""Tests for TOTP enrolment, recovery-code regeneration and status (#1177)."""

from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import decrypt_mfa_secret
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.models import (
    AuditLog,
    EmailOutbox,
    MfaRecoveryCode,
    RefreshToken,
    User,
    UserMfa,
)
from rs_shared.services.auth._mfa_codes import RECOVERY_CODE_COUNT
from rs_shared.services.auth.mfa import (
    confirm_enrolment,
    is_mfa_enabled,
    mfa_status,
    regenerate_recovery_codes,
    start_enrolment,
)
from rs_shared.services.exceptions import (
    InvalidMfaCodeError,
    MfaAlreadyEnabledError,
    MfaNotEnrolledError,
)


def _code(secret: str, offset: int = 0) -> str:
    return pyotp.TOTP(secret).at(datetime.now(timezone.utc), counter_offset=offset)


def _wrong(secret: str, offset: int = 0) -> str:
    return "000000" if _code(secret, offset) != "000000" else "111111"


async def _enrolled(session: AsyncSession, user: User) -> tuple[str, list[str]]:
    """Enrol ``user`` for real; returns (secret, recovery codes)."""
    async with transactional(session):
        secret, _ = await start_enrolment(session, user)
        codes = await confirm_enrolment(
            session, user, _code(secret), keep_session_id=None
        )
    return secret, codes


async def _refresh_row(session: AsyncSession, user_id: int) -> RefreshToken:
    row = RefreshToken(
        token_hash=f"h-{datetime.now(timezone.utc).timestamp()}-{user_id}",
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def _actions(session: AsyncSession) -> list[str]:
    rows = await session.execute(select(AuditLog.action))  # pyright: ignore[reportArgumentType]
    return [r[0] for r in rows.all()]


async def _subjects(session: AsyncSession) -> list[str]:
    rows = await session.execute(select(EmailOutbox.subject))  # pyright: ignore[reportArgumentType]
    return [r[0] for r in rows.all()]


# ── enrolment ────────────────────────────────────────────────────────────────


async def test_start_enrolment_stores_only_ciphertext(
    session: AsyncSession, admin_user: User
):
    secret, uri = await start_enrolment(session, admin_user)
    await session.commit()

    row = await session.get(UserMfa, admin_user.id)
    assert row is not None and row.enabled_at is None
    assert secret not in row.secret_encrypted
    assert decrypt_mfa_secret(row.secret_encrypted) == secret
    assert uri.startswith("otpauth://totp/") and f"secret={secret}" in uri
    assert not await is_mfa_enabled(session, admin_user.id)


async def test_restarting_enrolment_replaces_pending_secret(
    session: AsyncSession, admin_user: User
):
    first, _ = await start_enrolment(session, admin_user)
    second, _ = await start_enrolment(session, admin_user)
    await session.commit()

    assert first != second
    with pytest.raises(InvalidMfaCodeError):
        await confirm_enrolment(session, admin_user, _code(first), keep_session_id=None)


async def test_confirm_with_wrong_code_stays_pending(
    session: AsyncSession, admin_user: User
):
    secret, _ = await start_enrolment(session, admin_user)
    with pytest.raises(InvalidMfaCodeError):
        await confirm_enrolment(
            session, admin_user, _wrong(secret), keep_session_id=None
        )
    assert not await is_mfa_enabled(session, admin_user.id)


async def test_confirm_without_start_is_refused(
    session: AsyncSession, admin_user: User
):
    with pytest.raises(MfaNotEnrolledError):
        await confirm_enrolment(session, admin_user, "123456", keep_session_id=None)


async def test_confirm_enables_verifies_own_session_and_revokes_others(
    session: AsyncSession, admin_user: User
):
    assert admin_user.id is not None
    keep = await _refresh_row(session, admin_user.id)
    await _refresh_row(session, admin_user.id)  # another session: revoked

    async with transactional(session):
        secret, _ = await start_enrolment(session, admin_user)
        codes = await confirm_enrolment(
            session, admin_user, _code(secret), keep_session_id=keep.id
        )

    assert await is_mfa_enabled(session, admin_user.id)
    assert len(codes) == RECOVERY_CODE_COUNT == len(set(codes))
    stored = {
        r[0]
        for r in (await session.execute(select(MfaRecoveryCode.code_hash))).all()  # pyright: ignore[reportArgumentType]
    }
    assert len(stored) == RECOVERY_CODE_COUNT
    assert not set(codes) & stored  # hashed only
    rows = (await session.execute(select(RefreshToken))).scalars().all()
    assert [(r.id, r.mfa_verified) for r in rows] == [(keep.id, True)]
    assert "mfa_enrolled" in await _actions(session)
    assert any("אימות דו-שלבי הופעל" in s for s in await _subjects(session))


async def test_enrolling_twice_is_refused(session: AsyncSession, admin_user: User):
    await _enrolled(session, admin_user)
    with pytest.raises(MfaAlreadyEnabledError):
        await start_enrolment(session, admin_user)


# ── recovery code regeneration + status ──────────────────────────────────────


async def test_regenerate_replaces_all_codes_and_emails(
    session: AsyncSession, admin_user: User
):
    secret, old = await _enrolled(session, admin_user)
    async with transactional(session):
        new = await regenerate_recovery_codes(session, admin_user, _code(secret, 1))

    assert len(new) == RECOVERY_CODE_COUNT and not set(new) & set(old)
    assert "mfa_recovery_codes_regenerated" in await _actions(session)
    assert any("קודי שחזור חדשים" in s for s in await _subjects(session))


async def test_regenerate_requires_mfa_and_a_valid_code(
    session: AsyncSession, admin_user: User
):
    with pytest.raises(MfaNotEnrolledError):
        await regenerate_recovery_codes(session, admin_user, "123456")

    secret, _ = await _enrolled(session, admin_user)
    with pytest.raises(InvalidMfaCodeError):
        await regenerate_recovery_codes(session, admin_user, _wrong(secret, 1))


async def test_mfa_status_counts_unused_codes(session: AsyncSession, admin_user: User):
    assert admin_user.id is not None
    assert await mfa_status(session, admin_user.id) == (False, 0)

    await _enrolled(session, admin_user)
    assert await mfa_status(session, admin_user.id) == (True, RECOVERY_CODE_COUNT)
