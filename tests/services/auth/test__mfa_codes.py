"""Tests for the TOTP code primitives (skew window, format, recovery codes)."""

import re
from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import encrypt_mfa_secret
from rs_shared.models import User, UserMfa
from rs_shared.services.auth._mfa_codes import (
    _matching_step,
    _new_recovery_code,
    _normalize_recovery_code,
    check_totp,
)

# ── step matching (explicit clock, so no boundary flakiness) ─────────────────


def test_matching_step_accepts_one_step_of_skew_only():
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    now = datetime(2026, 11, 21, 12, 0, 10, tzinfo=timezone.utc)
    current = totp.timecode(now)

    for offset in (-1, 0, 1):
        code = totp.generate_otp(current + offset)
        assert _matching_step(secret, code, now) == current + offset
    for offset in (-2, 2):
        assert _matching_step(secret, totp.generate_otp(current + offset), now) is None


@pytest.mark.parametrize("bad", ["", "12345", "1234567", "abcdef", "12 34 5x"])
def test_matching_step_rejects_malformed_codes(bad: str):
    assert (
        _matching_step(pyotp.random_base32(), bad, datetime.now(timezone.utc)) is None
    )


def test_matching_step_tolerates_spaces():
    secret = pyotp.random_base32()
    now = datetime.now(timezone.utc)
    code = pyotp.TOTP(secret).at(now)
    assert _matching_step(secret, f"{code[:3]} {code[3:]}", now) is not None


async def test_check_totp_refuses_a_right_code_while_locked(
    session: AsyncSession, admin_user: User
):
    """The claim re-checks the lock: a guess racing the locking failure loses."""
    secret = pyotp.random_base32()
    now = datetime.now(timezone.utc)
    mfa = UserMfa(
        user_id=admin_user.id,
        secret_encrypted=encrypt_mfa_secret(secret),
        locked_until=now + timedelta(minutes=5),
    )
    session.add(mfa)
    await session.commit()
    totp = pyotp.TOTP(secret)

    assert not await check_totp(session, mfa, totp.at(now), now)
    # Once the lock is over, a code is accepted again.
    later = now + timedelta(minutes=5)
    assert await check_totp(session, mfa, totp.at(later), later)


def test_recovery_codes_are_grouped_and_unambiguous():
    code = _new_recovery_code()
    assert re.fullmatch(r"[a-z2-9]{5}-[a-z2-9]{5}", code)
    assert not set(code) & set("01loi")


def test_recovery_code_normalisation_ignores_case_dashes_and_spaces():
    assert _normalize_recovery_code(" ABCDE-fghjk ") == "abcdefghjk"


def test_recovery_code_hash_is_keyed_not_plain_sha256():
    import hashlib
    from unittest.mock import patch

    from rs_shared.core.infrastructure import security

    plain = hashlib.sha256(b"abcdefghjk").hexdigest()
    with patch.object(security.settings, "mfa_encryption_key", "k" * 40):
        first = security.hash_mfa_recovery_code("abcdefghjk")
    with patch.object(security.settings, "mfa_encryption_key", "z" * 40):
        second = security.hash_mfa_recovery_code("abcdefghjk")
    assert len(first) == 64 and first != plain and first != second
