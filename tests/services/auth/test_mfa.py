"""Tests for the TOTP second factor (#1177): enrolment, challenge, recovery."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pyotp
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import decrypt_mfa_secret
from rs_shared.models import (
    AuditLog,
    MfaChallenge,
    MfaRecoveryCode,
    RefreshToken,
    User,
    UserMfa,
)
from rs_shared.services.auth import mfa
from rs_shared.services.auth._mfa_codes import RECOVERY_CODE_COUNT
from rs_shared.services.auth.mfa import (
    MAX_CHALLENGE_FAILURES,
    confirm_enrolment,
    create_challenge,
    is_mfa_enabled,
    regenerate_recovery_codes,
    start_enrolment,
    verify_challenge,
)
from rs_shared.services.exceptions import (
    AccountLockedError,
    InvalidMfaCodeError,
    MfaAlreadyEnabledError,
    MfaChallengeExpiredError,
    MfaNotEnrolledError,
)

IP = "203.0.113.5"


def _code(secret: str, offset: int = 0) -> str:
    return pyotp.TOTP(secret).at(datetime.now(timezone.utc), counter_offset=offset)


async def _enrolled(session: AsyncSession, user: User) -> tuple[str, list[str]]:
    """Enrol ``user`` for real; returns (secret, recovery codes)."""
    secret, _ = await start_enrolment(session, user)
    codes = await confirm_enrolment(session, user, _code(secret), keep_session_id=None)
    await session.commit()
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
    wrong = "000000" if _code(secret) != "000000" else "111111"
    with pytest.raises(InvalidMfaCodeError):
        await confirm_enrolment(session, admin_user, wrong, keep_session_id=None)
    assert not await is_mfa_enabled(session, admin_user.id)


async def test_confirm_without_start_is_refused(
    session: AsyncSession, admin_user: User
):
    with pytest.raises(MfaNotEnrolledError):
        await confirm_enrolment(session, admin_user, "123456", keep_session_id=None)


async def test_confirm_enables_issues_codes_and_revokes_other_sessions(
    session: AsyncSession, admin_user: User
):
    assert admin_user.id is not None
    keep = await _refresh_row(session, admin_user.id)
    other = await _refresh_row(session, admin_user.id)

    secret, _ = await start_enrolment(session, admin_user)
    codes = await confirm_enrolment(
        session, admin_user, _code(secret), keep_session_id=keep.id
    )
    await session.commit()

    assert await is_mfa_enabled(session, admin_user.id)
    assert len(codes) == RECOVERY_CODE_COUNT == len(set(codes))
    stored = (await session.execute(select(MfaRecoveryCode.code_hash))).all()  # pyright: ignore[reportArgumentType]
    assert len(stored) == RECOVERY_CODE_COUNT
    assert not any(c in {s[0] for s in stored} for c in codes)  # hashed only
    remaining = {
        r[0]
        for r in (await session.execute(select(RefreshToken.id))).all()  # pyright: ignore[reportArgumentType]
    }
    assert keep.id in remaining and other.id not in remaining
    assert "mfa_enrolled" in await _actions(session)


async def test_enrolling_twice_is_refused(session: AsyncSession, admin_user: User):
    await _enrolled(session, admin_user)
    with pytest.raises(MfaAlreadyEnabledError):
        await start_enrolment(session, admin_user)


# ── login challenge ──────────────────────────────────────────────────────────


async def test_verify_with_code_succeeds_once_and_consumes_challenge(
    session: AsyncSession, admin_user: User
):
    secret, _ = await _enrolled(session, admin_user)
    raw = await create_challenge(session, admin_user, remember_me=True)
    await session.commit()

    # The confirm step already used the current step; the next one is fresh.
    user, remember_me = await verify_challenge(
        session, raw, code=_code(secret, offset=1), client_ip=IP
    )
    await session.commit()

    assert user.id == admin_user.id and remember_me is True
    assert (await session.execute(select(MfaChallenge))).first() is None
    with pytest.raises(MfaChallengeExpiredError):
        await verify_challenge(session, raw, code=_code(secret, 1), client_ip=IP)


async def test_replayed_code_is_rejected(session: AsyncSession, admin_user: User):
    secret, _ = await _enrolled(session, admin_user)
    code = _code(secret, offset=1)
    first = await create_challenge(session, admin_user, remember_me=False)
    await session.commit()
    await verify_challenge(session, first, code=code, client_ip=IP)
    await session.commit()

    second = await create_challenge(session, admin_user, remember_me=False)
    await session.commit()
    with pytest.raises(InvalidMfaCodeError):
        await verify_challenge(session, second, code=code, client_ip=IP)


async def test_bad_code_counts_on_challenge_audit_and_throttle(
    session: AsyncSession, admin_user: User
):
    secret, _ = await _enrolled(session, admin_user)
    raw = await create_challenge(session, admin_user, remember_me=False)
    await session.commit()
    wrong = "000000" if _code(secret, 1) != "000000" else "111111"

    with patch.object(
        mfa.login_throttle, "record_login_failure", new_callable=AsyncMock
    ) as record:
        with pytest.raises(InvalidMfaCodeError):
            await verify_challenge(session, raw, code=wrong, client_ip=IP)
    await session.rollback()

    record.assert_awaited_once_with(admin_user.email, IP)
    challenge = (await session.execute(select(MfaChallenge))).scalar_one()
    assert challenge.failed_attempts == 1
    assert "mfa_verify_failed" in await _actions(session)


async def test_challenge_dies_after_max_failures(
    session: AsyncSession, admin_user: User
):
    secret, _ = await _enrolled(session, admin_user)
    raw = await create_challenge(session, admin_user, remember_me=False)
    await session.execute(
        update(MfaChallenge).values(failed_attempts=MAX_CHALLENGE_FAILURES)
    )
    await session.commit()

    with pytest.raises(MfaChallengeExpiredError):
        await verify_challenge(session, raw, code=_code(secret, 1), client_ip=IP)


async def test_expired_challenge_is_refused(session: AsyncSession, admin_user: User):
    secret, _ = await _enrolled(session, admin_user)
    raw = await create_challenge(session, admin_user, remember_me=False)
    await session.execute(
        update(MfaChallenge).values(
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )
    )
    await session.commit()

    with pytest.raises(MfaChallengeExpiredError):
        await verify_challenge(session, raw, code=_code(secret, 1), client_ip=IP)


async def test_unknown_challenge_is_refused(session: AsyncSession):
    with pytest.raises(MfaChallengeExpiredError):
        await verify_challenge(session, "nope", code="123456", client_ip=IP)


async def test_throttled_pair_is_refused_before_code_check(
    session: AsyncSession, admin_user: User
):
    secret, _ = await _enrolled(session, admin_user)
    raw = await create_challenge(session, admin_user, remember_me=False)
    await session.commit()

    with patch.object(
        mfa.login_throttle,
        "check_login_allowed",
        new=AsyncMock(side_effect=AccountLockedError(1)),
    ):
        with pytest.raises(AccountLockedError):
            await verify_challenge(session, raw, code=_code(secret, 1), client_ip=IP)


async def test_recovery_code_works_once_and_is_audited(
    session: AsyncSession, admin_user: User
):
    _, codes = await _enrolled(session, admin_user)
    raw = await create_challenge(session, admin_user, remember_me=False)
    await session.commit()

    # Codes are accepted regardless of case and dash.
    typed = codes[0].upper().replace("-", "")
    user, _ = await verify_challenge(session, raw, recovery_code=typed, client_ip=IP)
    await session.commit()
    assert user.id == admin_user.id
    assert "mfa_recovery_code_used" in await _actions(session)

    again = await create_challenge(session, admin_user, remember_me=False)
    await session.commit()
    with pytest.raises(InvalidMfaCodeError):
        await verify_challenge(session, again, recovery_code=codes[0], client_ip=IP)


async def test_verify_without_any_code_fails(session: AsyncSession, admin_user: User):
    await _enrolled(session, admin_user)
    raw = await create_challenge(session, admin_user, remember_me=False)
    await session.commit()
    with pytest.raises(InvalidMfaCodeError):
        await verify_challenge(session, raw, client_ip=IP)


async def test_challenge_for_user_without_mfa_is_refused(
    session: AsyncSession, admin_user: User
):
    raw = await create_challenge(session, admin_user, remember_me=False)
    await session.commit()
    with pytest.raises(MfaChallengeExpiredError):
        await verify_challenge(session, raw, code="123456", client_ip=IP)


# ── recovery code regeneration ───────────────────────────────────────────────


async def test_regenerate_replaces_all_codes(session: AsyncSession, admin_user: User):
    secret, old = await _enrolled(session, admin_user)
    new = await regenerate_recovery_codes(session, admin_user, _code(secret, 1))
    await session.commit()

    assert len(new) == RECOVERY_CODE_COUNT and not set(new) & set(old)
    raw = await create_challenge(session, admin_user, remember_me=False)
    await session.commit()
    with pytest.raises(InvalidMfaCodeError):
        await verify_challenge(session, raw, recovery_code=old[0], client_ip=IP)


async def test_regenerate_requires_mfa_and_a_valid_code(
    session: AsyncSession, admin_user: User
):
    with pytest.raises(MfaNotEnrolledError):
        await regenerate_recovery_codes(session, admin_user, "123456")

    secret, _ = await _enrolled(session, admin_user)
    wrong = "000000" if _code(secret, 1) != "000000" else "111111"
    with pytest.raises(InvalidMfaCodeError):
        await regenerate_recovery_codes(session, admin_user, wrong)
