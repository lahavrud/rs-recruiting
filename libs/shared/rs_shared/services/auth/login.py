"""Login authentication logic: credential validation and lockout tracking.

Token issuance and rotation live in ``session.py``.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import get_password_hash, is_password_valid
from rs_shared.models import ActivationToken, User
from rs_shared.services.auth import login_throttle
from rs_shared.services.exceptions import (
    InvalidCredentialsError,
    PendingActivationError,
    PendingApprovalError,
)

logger = logging.getLogger(__name__)

# Pre-computed once at module load so authenticate_user takes ~100 ms
# regardless of whether the email exists, preventing timing-based email
# enumeration (comparing branch latency distinguishes "not found" from
# "wrong password" without this equalisation).
_DUMMY_HASH: str = get_password_hash("dummy-fixed-for-timing")


async def authenticate_user(
    email: str,
    password: str,
    session: AsyncSession,
    client_ip: str | None = None,
) -> User:
    """Authenticate a user by email and password.

    Failed attempts are throttled per (email, client IP) — see
    ``login_throttle``. Checking the throttle before bcrypt makes a blocked
    response faster than a wrong-password one, which reveals nothing new: the
    429 already says this source is blocked, and unknown emails are blocked the
    same way, so it is never an account-existence signal.
    """
    email = email.lower().strip()

    # Throttle first: a blocked (email, IP) pair gets AccountLockedError
    # without spending bcrypt, identically for unknown and real emails, and
    # the same account from any other address is unaffected
    # (see login_throttle for the policy).
    await login_throttle.check_login_allowed(email, client_ip)

    result = await session.execute(
        select(User).where(User.email == email)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one_or_none()
    if not user:
        is_password_valid(password, _DUMMY_HASH)  # equalise timing
        logger.warning("login_email_not_found", extra={"ip": client_ip})
        await login_throttle.record_login_failure(email, client_ip)
        raise InvalidCredentialsError("Incorrect email or password")

    if not is_password_valid(password, user.hashed_password):
        await login_throttle.record_login_failure(email, client_ip)
        raise InvalidCredentialsError("Incorrect email or password")

    if not user.is_active:
        # Distinguish: has a pending activation token → admin approved but company
        # hasn't clicked the link yet.  No token → still awaiting admin review.
        activation_result = await session.execute(
            select(ActivationToken).where(
                ActivationToken.user_id == user.id,  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
                ActivationToken.used == False,  # noqa: E712
            )
        )
        if activation_result.scalar_one_or_none() is not None:
            raise PendingActivationError("account_pending_activation")
        raise PendingApprovalError("account_pending_approval")

    await login_throttle.clear_login_failures(email, client_ip)
    return user
