"""Tests for the code step of an MFA login (#1177)."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pyotp
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.models import AuditLog, EmailOutbox, MfaChallenge, User, UserMfa
from rs_shared.services.auth import mfa_challenge
from rs_shared.services.auth.mfa import confirm_enrolment, start_enrolment
from rs_shared.services.auth.mfa_challenge import (
    MAX_CHALLENGE_ATTEMPTS,
    create_challenge,
    verify_challenge,
)
from rs_shared.services.exceptions import (
    AccountLockedError,
    InvalidMfaCodeError,
    MfaChallengeExpiredError,
    MfaLockedError,
)

IP = "203.0.113.5"


def _code(secret: str, offset: int = 0) -> str:
    return pyotp.TOTP(secret).at(datetime.now(timezone.utc), counter_offset=offset)


def _wrong(secret: str) -> str:
    valid = {_code(secret, o) for o in (-1, 0, 1)}
    return next(c for c in ("000000", "111111", "222222", "333333") if c not in valid)


async def _enrolled(session: AsyncSession, user: User) -> tuple[str, list[str]]:
    async with transactional(session):
        secret, _ = await start_enrolment(session, user)
        codes = await confirm_enrolment(
            session, user, _code(secret), keep_session_id=None
        )
    return secret, codes


async def _challenge(session: AsyncSession, user: User, remember_me=False) -> str:
    async with transactional(session):
        return await create_challenge(session, user, remember_me=remember_me)


async def _verify(session: AsyncSession, raw: str, **kwargs) -> tuple[User, bool]:
    async with transactional(session):
        return await verify_challenge(session, raw, client_ip=IP, **kwargs)


async def _actions(session: AsyncSession) -> list[str]:
    rows = await session.execute(select(AuditLog.action))  # pyright: ignore[reportArgumentType]
    return [r[0] for r in rows.all()]


async def test_code_succeeds_once_and_consumes_challenge(
    session: AsyncSession, admin_user: User
):
    secret, _ = await _enrolled(session, admin_user)
    raw = await _challenge(session, admin_user, remember_me=True)

    # The confirm step already used the current step; the next one is fresh.
    user, remember_me = await _verify(session, raw, code=_code(secret, 1))

    assert user.id == admin_user.id and remember_me is True
    assert (await session.execute(select(MfaChallenge))).first() is None
    with pytest.raises(MfaChallengeExpiredError):
        await _verify(session, raw, code=_code(secret, 1))


async def test_a_new_challenge_replaces_the_earlier_one(
    session: AsyncSession, admin_user: User
):
    secret, _ = await _enrolled(session, admin_user)
    earlier = await _challenge(session, admin_user)
    latest = await _challenge(session, admin_user)

    with pytest.raises(MfaChallengeExpiredError):
        await _verify(session, earlier, code=_code(secret, 1))
    user, _ = await _verify(session, latest, code=_code(secret, 1))
    assert user.id == admin_user.id


async def test_the_wrong_code_that_locks_reports_the_lock(
    session: AsyncSession, admin_user: User
):
    secret, _ = await _enrolled(session, admin_user)
    await session.execute(update(UserMfa).values(failed_attempts=4))
    await session.commit()

    with pytest.raises(MfaLockedError) as exc:
        await _verify(
            session, await _challenge(session, admin_user), code=_wrong(secret)
        )
    assert exc.value.minutes_remaining == 5


async def test_replayed_code_is_rejected(session: AsyncSession, admin_user: User):
    secret, _ = await _enrolled(session, admin_user)
    code = _code(secret, offset=1)
    await _verify(session, await _challenge(session, admin_user), code=code)

    with pytest.raises(InvalidMfaCodeError):
        await _verify(session, await _challenge(session, admin_user), code=code)


async def test_wrong_code_counts_everywhere(session: AsyncSession, admin_user: User):
    secret, _ = await _enrolled(session, admin_user)
    raw = await _challenge(session, admin_user)

    with patch(
        "rs_shared.services.auth._mfa_lockout.login_throttle.record_login_failure",
        new_callable=AsyncMock,
    ) as record:
        with pytest.raises(InvalidMfaCodeError):
            await _verify(session, raw, code=_wrong(secret))

    record.assert_awaited_once_with(admin_user.email, IP)
    session.expire_all()
    challenge = (await session.execute(select(MfaChallenge))).scalar_one()
    assert challenge.attempts == 1
    mfa = await session.get(UserMfa, admin_user.id)
    assert mfa is not None and mfa.failed_attempts == 1
    assert "mfa_verify_failed" in await _actions(session)


async def test_challenge_dies_after_max_attempts(
    session: AsyncSession, admin_user: User
):
    secret, _ = await _enrolled(session, admin_user)
    raw = await _challenge(session, admin_user)
    await session.execute(update(MfaChallenge).values(attempts=MAX_CHALLENGE_ATTEMPTS))
    await session.commit()

    with pytest.raises(MfaChallengeExpiredError):
        await _verify(session, raw, code=_code(secret, 1))


async def test_concurrent_guesses_cannot_overrun_attempt_cap(
    session: AsyncSession,
    admin_user: User,
    session_local_factory: async_sessionmaker[AsyncSession],
):
    secret, _ = await _enrolled(session, admin_user)
    raw = await _challenge(session, admin_user)

    async def guess() -> BaseException | None:
        async with session_local_factory() as s:
            try:
                await _verify(s, raw, code=_wrong(secret))
            except (
                InvalidMfaCodeError,
                MfaChallengeExpiredError,
                MfaLockedError,
            ) as exc:
                return exc
        return None

    results = await asyncio.gather(
        *(guess() for _ in range(2 * MAX_CHALLENGE_ATTEMPTS))
    )

    # Exactly MAX guesses got an attempt; the rest found the challenge used up.
    # (The 5th account failure locks, so some report the lock instead.)
    tried = [r for r in results if isinstance(r, (InvalidMfaCodeError, MfaLockedError))]
    assert len(tried) == MAX_CHALLENGE_ATTEMPTS
    session.expire_all()
    challenge = (await session.execute(select(MfaChallenge))).scalar_one()
    assert challenge.attempts == MAX_CHALLENGE_ATTEMPTS


async def test_concurrent_correct_answers_log_in_once(
    session: AsyncSession,
    admin_user: User,
    session_local_factory: async_sessionmaker[AsyncSession],
):
    _, codes = await _enrolled(session, admin_user)
    raw = await _challenge(session, admin_user)

    async def answer(recovery: str) -> bool:
        async with session_local_factory() as s:
            try:
                await _verify(s, raw, recovery_code=recovery)
            except MfaChallengeExpiredError:
                return False
        return True

    results = await asyncio.gather(answer(codes[0]), answer(codes[1]))

    assert sorted(results) == [False, True]
    # The loser's recovery code rolled back with it: still usable.
    session.expire_all()
    raw2 = await _challenge(session, admin_user)
    loser = codes[0] if results[1] else codes[1]
    user, _ = await _verify(session, raw2, recovery_code=loser)
    assert user.id == admin_user.id


async def test_expired_challenge_is_refused(session: AsyncSession, admin_user: User):
    secret, _ = await _enrolled(session, admin_user)
    raw = await _challenge(session, admin_user)
    await session.execute(
        update(MfaChallenge).values(
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )
    )
    await session.commit()

    with pytest.raises(MfaChallengeExpiredError):
        await _verify(session, raw, code=_code(secret, 1))


async def test_unknown_challenge_is_refused(session: AsyncSession):
    with pytest.raises(MfaChallengeExpiredError):
        await _verify(session, "nope", code="123456")


async def test_locked_account_is_refused_even_with_the_right_code(
    session: AsyncSession, admin_user: User
):
    secret, _ = await _enrolled(session, admin_user)
    raw = await _challenge(session, admin_user)
    await session.execute(
        update(UserMfa).values(
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=3)
        )
    )
    await session.commit()

    with pytest.raises(MfaLockedError) as exc:
        await _verify(session, raw, code=_code(secret, 1))
    assert exc.value.minutes_remaining == 3


async def test_right_code_clears_the_account_count(
    session: AsyncSession, admin_user: User
):
    secret, _ = await _enrolled(session, admin_user)
    await session.execute(update(UserMfa).values(failed_attempts=3))
    await session.commit()

    await _verify(session, await _challenge(session, admin_user), code=_code(secret, 1))

    session.expire_all()
    mfa = await session.get(UserMfa, admin_user.id)
    assert mfa is not None and mfa.failed_attempts == 0 and mfa.locked_until is None


async def test_throttled_pair_is_refused_before_code_check(
    session: AsyncSession, admin_user: User
):
    secret, _ = await _enrolled(session, admin_user)
    raw = await _challenge(session, admin_user)

    with patch.object(
        mfa_challenge.login_throttle,
        "check_login_allowed",
        new=AsyncMock(side_effect=AccountLockedError(1)),
    ):
        with pytest.raises(AccountLockedError):
            await _verify(session, raw, code=_code(secret, 1))


async def test_recovery_code_works_once_is_audited_and_emailed(
    session: AsyncSession, admin_user: User
):
    _, codes = await _enrolled(session, admin_user)

    # Codes are accepted regardless of case and dash.
    typed = codes[0].upper().replace("-", "")
    user, _ = await _verify(
        session, await _challenge(session, admin_user), recovery_code=typed
    )
    assert user.id == admin_user.id
    assert "mfa_recovery_code_used" in await _actions(session)
    bodies = (await session.execute(select(EmailOutbox.body))).scalars().all()  # pyright: ignore[reportArgumentType]
    assert any("נותרו 9 קודים" in b for b in bodies)

    with pytest.raises(InvalidMfaCodeError):
        await _verify(
            session, await _challenge(session, admin_user), recovery_code=codes[0]
        )


async def test_challenge_for_user_without_mfa_is_refused(
    session: AsyncSession, admin_user: User
):
    raw = await _challenge(session, admin_user)
    with pytest.raises(MfaChallengeExpiredError):
        await _verify(session, raw, code="123456")
