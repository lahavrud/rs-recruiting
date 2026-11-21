"""Model tests for the MFA tables (UserMfa, MfaRecoveryCode, MfaChallenge)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from rs_shared.models import MfaChallenge, MfaRecoveryCode, User, UserMfa


@pytest.mark.asyncio
async def test_user_mfa_defaults_to_pending(session, admin_user: User):
    session.add(UserMfa(user_id=admin_user.id, secret_encrypted="ct"))
    await session.commit()

    row = await session.get(UserMfa, admin_user.id)
    assert row is not None
    assert row.enabled_at is None
    assert row.last_used_step == 0


@pytest.mark.asyncio
async def test_recovery_code_hash_is_unique(session, admin_user: User):
    session.add(MfaRecoveryCode(user_id=admin_user.id, code_hash="a" * 64))
    await session.flush()
    session.add(MfaRecoveryCode(user_id=admin_user.id, code_hash="a" * 64))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_deleting_user_cascades_all_mfa_rows(session, admin_user: User):
    session.add(UserMfa(user_id=admin_user.id, secret_encrypted="ct"))
    session.add(MfaRecoveryCode(user_id=admin_user.id, code_hash="b" * 64))
    session.add(
        MfaChallenge(
            token_hash="c" * 64,
            user_id=admin_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
    )
    await session.commit()

    await session.execute(delete(User).where(User.id == admin_user.id))  # pyright: ignore[reportArgumentType]
    await session.commit()

    for model in (UserMfa, MfaRecoveryCode, MfaChallenge):
        assert (await session.execute(select(model))).first() is None


def test_table_names_match_migration():
    """Kept in step with alembic a7c4e91b2d58 (create_all builds dev/test)."""
    assert UserMfa.__table__.name == "user_mfa"  # type: ignore[attr-defined]
    assert MfaRecoveryCode.__table__.name == "mfa_recovery_code"  # type: ignore[attr-defined]
    assert MfaChallenge.__table__.name == "mfa_challenge"  # type: ignore[attr-defined]
