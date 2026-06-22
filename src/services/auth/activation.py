"""Account-activation token consumption.

Originally carved out next to the admin company lifecycle code that mints
these tokens (`admin_companies.approve_company`). The service also serves
candidate self-registration tokens — the dispatch happens on `User.role`:

* COMPANY: legacy path — just flip `is_active=True`. Consent is recorded
  on `CompanyProfile` at registration time, not here.
* CANDIDATE: create or link the `CandidateProfile` for the activating
  user's email, write consent fields using the activation request's
  IP / user-agent, then flip `is_active=True`. The post-activation
  explainer email is enqueued by the router using `defer_after_commit`.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.security import hash_token
from src.enums import UserRole
from src.models import ActivationToken, CandidateProfile, User
from src.services.exceptions import InvalidActivationTokenError
from src.services.utils.audit import record_audit_event
from src.services.utils.legal import (
    CURRENT_PRIVACY_POLICY_VERSION,
    CURRENT_TERMS_OF_SERVICE_VERSION,
)


async def activate_user(
    token: str,
    session: AsyncSession,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> User:
    """Activate a user account using the one-time activation token.

    Dispatches on `User.role`:
    * COMPANY → flips `is_active=True` (consent already on CompanyProfile).
    * CANDIDATE → ensures a CandidateProfile exists for this user's email
      (creating one or linking an existing anonymous-lead profile),
      writes consent fields using the activation request's IP/UA, then
      flips `is_active=True`.

    Raises:
        InvalidActivationTokenError: If the token is invalid, expired, or
            already used.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(ActivationToken, User)
        .join(User, User.id == ActivationToken.user_id)  # pyright: ignore[reportArgumentType]
        .where(ActivationToken.token_hash == hash_token(token))  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
    )
    row = result.one_or_none()

    if row is None:
        raise InvalidActivationTokenError("הקישור אינו תקף או שכבר נעשה בו שימוש")
    activation, user = row
    if activation.used:
        raise InvalidActivationTokenError("הקישור אינו תקף או שכבר נעשה בו שימוש")
    if activation.expires_at.replace(tzinfo=timezone.utc) < now:
        raise InvalidActivationTokenError("פג תוקף הקישור")

    if user.role == UserRole.CANDIDATE:
        await _link_or_create_candidate_profile(
            user,
            activation,
            session,
            now=now,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    user.is_active = True
    activation.used = True
    return user


# Backwards-compatibility alias — keeps the existing /activate router and
# tests importing `activate_company` working unchanged. The role dispatch
# inside `activate_user` makes the function name slightly misleading for
# candidate tokens, but the underlying behavior is correct for both flows.
activate_company = activate_user


async def _link_or_create_candidate_profile(
    user: User,
    activation: ActivationToken,
    session: AsyncSession,
    *,
    now: datetime,
    ip_address: str | None,
    user_agent: str | None,
) -> CandidateProfile:
    """Ensure a CandidateProfile exists for the activating user.

    If an anonymous-lead profile already exists for the user's email (e.g.
    they applied to a job before registering), link it to the user. Otherwise
    create a fresh profile with a minimal `full_name` placeholder so the
    NOT-NULL invariant holds; the candidate fills in the rest from the
    profile page.

    Always (re)writes consent fields from the activation-request context,
    using the policy version snapshotted on the activation token if present.
    """
    result = await session.execute(
        select(CandidateProfile)
        .options(selectinload(CandidateProfile.user))
        .where(CandidateProfile.email == user.email)  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
    )
    profile = result.scalar_one_or_none()

    policy_version = activation.consent_policy_version or CURRENT_PRIVACY_POLICY_VERSION
    # Prefer the name snapshotted on the activation token (set at
    # registration time, Sprint 11 / candidate-activation-followups).
    # Fall back to the local-part of the email for tokens minted before
    # the column existed.
    full_name = activation.full_name or user.email.split("@", 1)[0]

    if profile is None:
        # Phone stays NULL — it's optional on the model now and the candidate
        # will supply it either via the profile page or inline when they hit
        # the apply form. The "phone is required for a live application"
        # invariant lives at the apply endpoint, not here.
        profile = CandidateProfile(
            user_id=user.id,
            full_name=full_name,
            email=user.email,
            phone=None,
            consent_given_at=now,
            consent_policy_version=policy_version,
            consent_ip=ip_address,
            consent_user_agent=user_agent,
            tos_accepted_at=now,
            tos_version=CURRENT_TERMS_OF_SERVICE_VERSION,
        )
        session.add(profile)
    else:
        profile.user_id = user.id
        profile.consent_given_at = now
        profile.consent_policy_version = policy_version
        profile.consent_ip = ip_address
        profile.consent_user_agent = user_agent
        profile.tos_accepted_at = now
        profile.tos_version = CURRENT_TERMS_OF_SERVICE_VERSION

    await session.flush()

    await record_audit_event(
        session,
        actor_user_id=user.id,
        action="candidate_activated",
        target_type="User",
        target_id=user.id,
        detail=f"policy_version={policy_version}",
        ip_address=ip_address,
    )

    return profile
