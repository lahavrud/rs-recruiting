"""Break-glass MFA reset (#1177): the only way to turn an admin's MFA off.

For a lost authenticator *and* lost recovery codes, or after a rotation of
MFA_ENCRYPTION_KEY made the stored secrets unreadable. Run by an operator via
``scripts/reset_mfa.py`` (in prod: a one-off ECS task, see
``docs/runbooks/mfa-reset.md``), never from an endpoint.

Removes the user's TOTP secret, recovery codes and pending challenges and ends
every session, so the next login is password-only and lands on enrolment.
The owner is emailed: a reset nobody asked for must not go unnoticed.
"""

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import MfaChallenge, MfaRecoveryCode, RefreshToken, User, UserMfa
from rs_shared.services.auth._mfa_notify import MfaEvent, notify_mfa_event
from rs_shared.services.utils.audit import record_audit_event

logger = logging.getLogger(__name__)


async def reset_user_mfa(session: AsyncSession, email: str, *, reason: str) -> bool:
    """Wipe ``email``'s MFA state and sessions. False if no such user.

    Must run inside ``transactional()``; the audit row and the owner's email
    commit with the reset.
    """
    user = (
        await session.execute(
            select(User).where(User.email == email.lower().strip())  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one_or_none()
    if user is None or user.id is None:
        return False

    for model in (UserMfa, MfaRecoveryCode, MfaChallenge, RefreshToken):
        await session.execute(
            delete(model).where(model.user_id == user.id)  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]
        )
    await record_audit_event(
        session,
        actor_user_id=None,
        action="mfa_reset_break_glass",
        target_type="User",
        target_id=user.id,
        detail=reason[:500],
    )
    await notify_mfa_event(session, user.email, MfaEvent.RESET)
    logger.warning("mfa_reset_break_glass", extra={"user_id": user.id})
    return True
