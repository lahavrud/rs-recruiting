"""Candidate self-registration service.

Two entry points:

* ``register_candidate`` — handles the public POST /auth/candidate/register
  form. Creates `User(role=CANDIDATE, is_active=False)` (or re-uses an
  existing unactivated row, replacing its password), kills any stale
  unused activation tokens, mints a fresh 2-hour token, and enqueues the
  activation email. The `CandidateProfile` itself is created at activation
  time (see `activate_user`), so failed registrations do not litter the
  admin candidate list.

* ``resend_candidate_activation`` — handles POST /auth/candidate/resend-activation.
  Silent 202 either way; mints a fresh token only when a candidate user
  exists with `is_active=False`. Both per-email and per-IP throttling are
  Redis-backed to prevent inbox flooding.

All audit + email enqueue calls go through the existing app infrastructure;
the rate-limit constants are colocated below so future tuning is one read.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.security import (
    get_password_hash,
    hash_token,
)
from src.core.infrastructure.transactions import defer_after_commit
from src.core.tasks import enqueue_email_task
from src.enums import UserRole
from src.models import ActivationToken, User
from src.services.exceptions import EmailAlreadyExistsError
from src.services.utils.audit import record_audit_event
from src.services.utils.legal import CURRENT_PRIVACY_POLICY_VERSION
from src.templates.email import build_candidate_activation_html

logger = logging.getLogger(__name__)

# Sprint 11 spec: candidates get a shorter window than companies (48h).
_CANDIDATE_ACTIVATION_TTL_HOURS = 2

# Per-email resend throttle. slowapi handles per-IP (5/hour) — this DB
# counter prevents an attacker on multiple IPs from inbox-flooding a victim.
_RESEND_PER_EMAIL_LIMIT = 1
_RESEND_WINDOW = timedelta(hours=1)


async def _check_resend_rate_limit(user_id: int, session: AsyncSession) -> bool:
    """Return True if the user is under the per-email resend quota (1/hour).

    Counts ActivationToken rows minted in the last hour. A small parallel-
    request window exists but is covered by the per-IP slowapi limit.
    """
    window_start = datetime.now(timezone.utc) - _RESEND_WINDOW
    result = await session.execute(
        select(func.count())
        .select_from(ActivationToken)
        .where(
            ActivationToken.user_id == user_id,  # type: ignore[arg-type]
            ActivationToken.created_at > window_start,
        )
    )
    return result.scalar_one() < _RESEND_PER_EMAIL_LIMIT


def _build_activation_url(raw_token: str) -> str:
    return f"{settings.frontend_base_url}/activate?token={raw_token}"


def _mint_activation_token(
    user_id: int,
    *,
    policy_version: str,
    full_name: str | None = None,
) -> tuple[str, ActivationToken]:
    """Generate a raw token + matching ActivationToken row (caller commits)."""
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=_CANDIDATE_ACTIVATION_TTL_HOURS
    )
    activation = ActivationToken(
        token_hash=hash_token(raw_token),
        user_id=user_id,
        expires_at=expires_at,
        consent_policy_version=policy_version,
        full_name=full_name,
    )
    return raw_token, activation


async def _latest_unused_full_name(user_id: int, session: AsyncSession) -> str | None:
    """Return ``full_name`` from this user's most recent unused token, if any.

    Used by the resend-activation path so the fresh token inherits the name
    the candidate originally supplied at registration. Returns None when no
    unused token exists or the value was never set (legacy rows minted
    before the column existed).
    """
    row = (
        await session.execute(
            select(ActivationToken.full_name)
            .where(
                ActivationToken.user_id == user_id,  # type: ignore[arg-type]
                ActivationToken.used == False,  # noqa: E712
            )
            .order_by(ActivationToken.created_at.desc())
            .limit(1)
        )
    ).first()
    return row[0] if row is not None else None


async def _delete_stale_tokens(user_id: int, session: AsyncSession) -> None:
    """Drop any prior unused ActivationToken rows for a user.

    Used by both re-registration (so the old link in the candidate's inbox
    stops working when they submit a new password) and resend-activation
    (mint-fresh semantics — only one valid token at a time).
    """
    stale_result = await session.execute(
        select(ActivationToken).where(
            ActivationToken.user_id == user_id,  # type: ignore[arg-type]
            ActivationToken.used == False,  # noqa: E712
        )
    )
    for stale in stale_result.scalars().all():
        await session.delete(stale)
    await session.flush()


def _send_activation_email_deferred(email: str, raw_token: str) -> None:
    """Schedule the activation email to fire after commit."""
    activation_url = _build_activation_url(raw_token)
    plain = (
        "שלום,\n\n"
        "תודה על ההרשמה ל-RS Recruiting.\n\n"
        f"להפעלת החשבון שלכם, לחצו על הקישור הבא בתוך שעתיים:\n{activation_url}\n\n"
        "אם לא התכוונתם להירשם, אפשר להתעלם מהמייל הזה.\n\n"
        "בברכה,\nצוות RS Recruiting"
    )
    html = build_candidate_activation_html(
        activation_url=activation_url,
        ttl_hours=_CANDIDATE_ACTIVATION_TTL_HOURS,
    )

    async def _send() -> None:
        try:
            await enqueue_email_task(
                to=email,
                subject="הפעלת חשבון מועמד – RS Recruiting",
                body=plain,
                html_body=html,
            )
        except Exception:
            logger.exception("Failed to enqueue candidate activation email")

    defer_after_commit(_send)


async def register_candidate(
    email: str,
    password: str,
    full_name: str,
    *,
    privacy_accepted: bool,
    terms_accepted: bool,
    session: AsyncSession,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Create or recycle a pending candidate user + send activation email.

    Behavior:
    * No matching user → create ``is_active=False`` row + mint a token,
      stash full_name on the token, email it, write the audit row.
    * Email matches an ``is_active=False`` candidate → recycle: update
      password, drop stale tokens, mint fresh, email it, audit it.
    * Email matches an ``is_active=True`` user → raise
      ``EmailAlreadyExistsError`` (router maps to 409). This explicit
      signal is the user-facing UX choice — we prefer to tell the user
      "this email is already registered, please log in" rather than
      silently swallow the attempt. Enumeration is partially mitigated
      by slowapi's 3/hour per-IP rate limit on the route.
    * Email matches an inactive non-candidate (e.g. a pending company)
      → ``EmailAlreadyExistsError`` for the same UX reason; we still
      refuse to hijack the slot for the candidate flow.

    Caller is responsible for the outer transaction (the router wraps this
    in ``transactional(session)``).
    """
    if not privacy_accepted or not terms_accepted:
        # Defense-in-depth — the router also enforces this on the API surface.
        raise ValueError("privacy_and_terms_required")

    normalized_email = email.lower().strip()

    result = await session.execute(
        select(User).where(User.email == normalized_email)  # type: ignore[arg-type]
    )
    existing = result.scalar_one_or_none()

    if existing is not None and existing.is_active:
        raise EmailAlreadyExistsError(normalized_email)

    if existing is not None and existing.role != UserRole.CANDIDATE:
        # Pending company / admin slot — don't let candidate flow hijack it.
        raise EmailAlreadyExistsError(normalized_email)

    if existing is None:
        user = User(
            email=normalized_email,
            hashed_password=get_password_hash(password),
            role=UserRole.CANDIDATE,
            is_active=False,
        )
        session.add(user)
        await session.flush()
    else:
        user = existing
        user.hashed_password = get_password_hash(password)
        await _delete_stale_tokens(user.id, session)

    assert user.id is not None
    raw_token, activation = _mint_activation_token(
        user.id,
        policy_version=CURRENT_PRIVACY_POLICY_VERSION,
        full_name=full_name,
    )
    session.add(activation)
    await session.flush()

    # Also stash full_name on the audit detail so it's recoverable if the
    # registration is abandoned and the User is later cleaned up by cron;
    # the canonical read at activation pulls from ActivationToken.full_name.
    await record_audit_event(
        session,
        actor_user_id=user.id,
        action="candidate_register_requested",
        target_type="User",
        target_id=user.id,
        detail=(
            f"policy_version={CURRENT_PRIVACY_POLICY_VERSION};full_name={full_name}"
        ),
        ip_address=ip_address,
    )

    _send_activation_email_deferred(normalized_email, raw_token)


async def resend_candidate_activation(
    email: str,
    *,
    session: AsyncSession,
    ip_address: str | None = None,
) -> None:
    """Resend the candidate activation email if applicable.

    Silent in all branches — caller maps to 202 regardless. Mints a fresh
    token only when a candidate user exists with `is_active=False`.
    Per-email rate-limited via DB count (caller handles per-IP via slowapi).
    """
    normalized_email = email.lower().strip()

    result = await session.execute(
        select(User).where(User.email == normalized_email)  # type: ignore[arg-type]
    )
    user = result.scalar_one_or_none()

    if user is None or user.role != UserRole.CANDIDATE or user.is_active:
        return

    assert user.id is not None
    if not await _check_resend_rate_limit(user.id, session):
        logger.warning(
            "candidate_resend_rate_limited",
            extra={"email_prefix": normalized_email.split("@", 1)[0][:2] + "***"},
        )
        return

    # Carry the original full_name from the prior unused token into the
    # fresh one so activation can still prefill CandidateProfile.full_name
    # without asking the candidate to retype their name on a resend.
    prior_full_name = await _latest_unused_full_name(user.id, session)
    await _delete_stale_tokens(user.id, session)
    raw_token, activation = _mint_activation_token(
        user.id,
        policy_version=CURRENT_PRIVACY_POLICY_VERSION,
        full_name=prior_full_name,
    )
    session.add(activation)
    await session.flush()

    await record_audit_event(
        session,
        actor_user_id=user.id,
        action="candidate_resend_activation_requested",
        target_type="User",
        target_id=user.id,
        ip_address=ip_address,
    )

    _send_activation_email_deferred(normalized_email, raw_token)
