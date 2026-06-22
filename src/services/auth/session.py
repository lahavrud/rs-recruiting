"""Token lifecycle: issuance, rotation, replay detection, and logout.

Login credential validation and lockout tracking live in ``login.py``.
Company registration lives in ``registration.py``.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import (
    create_access_token,
    create_refresh_token,
    hash_token,
)
from src.enums import InviteTokenStatus
from src.models import (
    InviteToken,
    RefreshToken,
    UsedRefreshToken,
    User,
)
from src.services.exceptions import InvalidCredentialsError
from src.services.utils.audit import record_audit_event

logger = logging.getLogger(__name__)


async def _delete_refresh_token(token_id: int) -> None:
    """Delete a refresh-token row in its own committed session.

    Must be used instead of ``session.delete()`` on the main request session
    when an exception is raised afterwards inside a ``transactional()`` block,
    because ``transactional()`` rolls back ALL pending changes on any exception.
    Using a separate session here (same pattern as ``_record_failed_attempt``)
    ensures the row is actually removed regardless of the outer transaction fate.

    Uses a direct DELETE statement (no prior SELECT) — idempotent if the row
    was already removed by a concurrent request.
    """
    from src.core.infrastructure.database import async_session as _session_factory

    async with _session_factory() as cleanup_session:
        await cleanup_session.execute(
            sa_delete(RefreshToken).where(
                RefreshToken.id == token_id  # pyright: ignore[reportArgumentType]
            )
        )
        await cleanup_session.commit()


async def _nuke_user_refresh_tokens(user_id: int) -> None:
    """Delete every active refresh token for a user on replay detection.

    Uses its own committed session for the same reason as ``_delete_refresh_token``:
    the caller raises ``InvalidCredentialsError`` afterwards, which rolls back the
    outer transactional() session and would undo a plain session.execute() delete.
    """
    from src.core.infrastructure.database import async_session as _session_factory

    async with _session_factory() as nuke_session:
        await nuke_session.execute(
            sa_delete(RefreshToken).where(
                RefreshToken.user_id == user_id  # pyright: ignore[reportArgumentType]
            )
        )
        await nuke_session.commit()


async def create_user_tokens(
    user: User, session: AsyncSession, *, remember_me: bool = False
) -> tuple[str, str]:
    """Issue a new access + refresh token pair.

    Returns (access_token, raw_refresh_token).
    """
    assert user.id is not None
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value}
    )

    raw_refresh, hashed_refresh, expires_at = create_refresh_token(
        remember_me=remember_me
    )
    db_token = RefreshToken(
        token_hash=hashed_refresh,
        user_id=user.id,
        expires_at=expires_at,
        remember_me=remember_me,
    )
    session.add(db_token)

    return access_token, raw_refresh


async def refresh_user_tokens(
    raw_refresh_token: str, session: AsyncSession
) -> tuple[str, str, bool]:
    """Validate and rotate a refresh token.

    Returns (new_access_token, new_raw_refresh_token, remember_me).
    remember_me is carried through from the original login so cookie
    persistence survives token rotation.
    """
    token_hash = hash_token(raw_refresh_token)

    # Replay detection: if this hash appears in the used-token store, an
    # already-consumed token has been presented again — strong signal of theft.
    # Expired used-hash records are cleaned up passively here; bulk cleanup
    # is left for a future scheduled job.
    used_result = await session.execute(
        select(UsedRefreshToken).where(
            UsedRefreshToken.token_hash == token_hash  # pyright: ignore[reportArgumentType]
        )
    )
    used_record = used_result.scalar_one_or_none()
    if used_record is not None:
        if used_record.expires_at > datetime.now(timezone.utc):
            # Two simultaneous refresh requests sharing one token will also trip
            # this path — accepted trade-off of single-use rotation.
            await _nuke_user_refresh_tokens(used_record.user_id)
            logger.warning(
                "refresh_token_replay_detected",
                extra={"user_id": used_record.user_id},
            )
            raise InvalidCredentialsError("Invalid or expired refresh token")
        else:
            await session.delete(used_record)

    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash  # pyright: ignore[reportArgumentType]
        )
    )
    db_token = result.scalar_one_or_none()

    if db_token is None:
        raise InvalidCredentialsError("Invalid or expired refresh token")

    # Expired-on-discovery rows are deleted on the way out so the
    # ``refreshtoken`` table doesn't accumulate dead state without a
    # cleanup path. Uses a separate committed session because
    # the outer transactional() block rolls back on the InvalidCredentialsError
    # that follows — a plain session.delete() would be undone. The HTTP
    # behaviour is unchanged — the caller still gets 401.
    if db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        assert db_token.id is not None
        await _delete_refresh_token(db_token.id)
        raise InvalidCredentialsError("Invalid or expired refresh token")

    user_result = await session.execute(
        select(User).where(User.id == db_token.user_id)  # pyright: ignore[reportArgumentType]
    )
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        assert db_token.id is not None
        await _delete_refresh_token(db_token.id)
        raise InvalidCredentialsError("Invalid or expired refresh token")

    remember_me = db_token.remember_me

    # Rotate: delete the consumed token and record its hash atomically so a
    # later replay is detected.
    session.add(
        UsedRefreshToken(
            token_hash=db_token.token_hash,
            user_id=db_token.user_id,
            expires_at=db_token.expires_at,
        )
    )
    await session.delete(db_token)
    await session.flush()

    access_token, raw_refresh = await create_user_tokens(
        user, session, remember_me=remember_me
    )
    return access_token, raw_refresh, remember_me


async def logout_user(
    raw_refresh_token: str | None,
    session: AsyncSession,
) -> None:
    """End the session: delete the refresh-token row.

    The 10-minute access token TTL (shortened from 30 min as part of the
    Redis removal) is the accepted tolerance window after logout.
    """
    if raw_refresh_token:
        token_hash = hash_token(raw_refresh_token)
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash  # pyright: ignore[reportArgumentType]
            )
        )
        db_token = result.scalar_one_or_none()
        if db_token is not None:
            session.add(
                UsedRefreshToken(
                    token_hash=db_token.token_hash,
                    user_id=db_token.user_id,
                    expires_at=db_token.expires_at,
                )
            )
            await session.delete(db_token)


async def get_invite_by_hash(token: str, session: AsyncSession) -> InviteToken | None:
    """Look up an invite token record by its hashed value, or None."""
    result = await session.execute(
        select(InviteToken).where(InviteToken.token_hash == hash_token(token))  # type: ignore[arg-type]
    )
    return result.scalar_one_or_none()


async def mark_invite_used(token: str, session: AsyncSession) -> None:
    """Mark the invite DB record as used after successful registration."""
    result = await session.execute(
        select(InviteToken).where(InviteToken.token_hash == hash_token(token))  # type: ignore[arg-type]
    )
    record = result.scalar_one_or_none()
    if record and record.status == InviteTokenStatus.PENDING:
        record.status = InviteTokenStatus.USED
        record.used_at = datetime.now(timezone.utc)
        session.add(record)
        await record_audit_event(
            session,
            actor_user_id=None,
            action="invite_used",
            target_type="invite",
            target_id=record.id,
            detail=record.email,
        )
