"""FastAPI dependencies for authentication and authorization."""

import ipaddress
from typing import Any

import sentry_sdk
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import get_session
from src.core.infrastructure.security import decode_access_token
from src.enums import UserRole
from src.models import CandidateProfile, CompanyProfile, User

security = HTTPBearer()

# Optional auth: returns the credential or None when no Authorization header is
# present. Used by public endpoints that *can* be enriched for logged-in users
# but must not 401 anonymous traffic (e.g. GET /api/public/jobs/:id with
# my_application surfacing for authenticated candidates).
security_optional = HTTPBearer(auto_error=False)


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """Decode and validate an access token, returning the payload.

    Raises 401 if the token is invalid or expired.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def get_current_user(
    payload: dict[str, Any] = Depends(get_token_payload),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Get current authenticated user from the validated JWT payload."""
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await session.execute(
        select(User).where(User.id == user_id_int)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Attach user to the current Sentry scope so any exception raised later
    # in this request gets tagged with them. No-op when Sentry isn't init'd.
    sentry_sdk.set_user({"id": str(user.id), "role": user.role.value})

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_optional),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Resolve the current authenticated user when a valid token is present;
    return ``None`` for anonymous requests.

    Differs from ``get_current_user`` in three ways:

    * Missing ``Authorization`` header → ``None`` (no 401).
    * Invalid / expired / blacklisted token → ``None`` (no 401).
    * Redis outage during blacklist check → ``None`` (degrade open — the
      caller is a public endpoint, so we'd rather skip personalization
      than fail closed).

    For inactive accounts we still return ``None`` rather than 403 — a
    public endpoint that incidentally identifies the requester shouldn't
    surface their activation state.
    """
    if credentials is None:
        return None

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return None

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        return None
    try:
        user_id_int = int(user_id_raw)
    except (ValueError, TypeError):
        return None

    result = await session.execute(
        select(User).where(User.id == user_id_int)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current authenticated admin user.

    This dependency ensures the current user has ADMIN role.
    Use this for admin-only endpoints.

    Args:
        current_user: Current authenticated user (from get_current_user)

    Returns:
        User with ADMIN role

    Raises:
        HTTPException: If user is not an admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def get_current_company(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> tuple[User, CompanyProfile]:
    """Get current authenticated company user and their company profile.

    This dependency ensures the current user has COMPANY role and is active.
    Returns both the user and their company profile for convenience.

    Args:
        current_user: Current authenticated user (from get_current_user)
        session: Database session

    Returns:
        Tuple of (User, CompanyProfile)

    Raises:
        HTTPException: If user is not a company or company profile not found
    """
    if current_user.role != UserRole.COMPANY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company access required",
        )

    # Get company profile
    result = await session.execute(
        select(CompanyProfile).where(
            CompanyProfile.user_id == current_user.id  # type: ignore[comparison-overlap]
        )
    )
    company_profile = result.scalar_one_or_none()
    if not company_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found",
        )

    # Validate company profile has an ID
    if company_profile.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Company profile ID is missing",
        )

    return (current_user, company_profile)


async def get_current_candidate(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> tuple[User, CandidateProfile]:
    """Get current authenticated candidate user and their candidate profile.

    Ensures the current user has CANDIDATE role and is active. Returns both
    the user and their candidate profile for convenience — mirrors
    `get_current_company`.

    Raises 403 if the user is not a candidate, 404 if their profile is not
    yet linked (defensive — should not happen post-activation since the
    activation flow creates / links the profile).
    """
    if current_user.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate access required",
        )

    result = await session.execute(
        select(CandidateProfile).where(
            CandidateProfile.user_id == current_user.id  # type: ignore[comparison-overlap]
        )
    )
    candidate_profile = result.scalar_one_or_none()
    if not candidate_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not found",
        )

    if candidate_profile.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Candidate profile ID is missing",
        )

    return (current_user, candidate_profile)


def _is_trusted_proxy(peer_ip: str) -> bool:
    """Return True if peer_ip falls within settings.trusted_proxy_ips."""
    raw = settings.trusted_proxy_ips.strip()
    if not raw:
        return False
    try:
        addr = ipaddress.ip_address(peer_ip)
        for cidr in raw.split(","):
            cidr = cidr.strip()
            if cidr and addr in ipaddress.ip_network(cidr, strict=False):
                return True
    except ValueError:
        pass
    return False


def client_ip(request: Request) -> str | None:
    """Best-effort client IP.

    Two-layer protection against XFF forgery:

    1. **Infrastructure layer (primary)**: set the `FORWARDED_ALLOW_IPS` env
       var to the load-balancer's private CIDR in production.  Uvicorn reads
       this automatically and only rewrites `request.client.host` from XFF when
       the TCP peer matches.  The value must mirror `TRUSTED_PROXY_IPS`.

    2. **Application layer (defence-in-depth)**: this function only reads
       `X-Forwarded-For` when `request.client.host` is in `TRUSTED_PROXY_IPS`.
       This layer is the sole guard when uvicorn's proxy middleware is not active
       (e.g. the httpx ASGITransport used in the test suite) and a second check
       for misconfigured deployments.

    Falls back to `request.client.host` — which is the uvicorn-resolved peer
    address — when no trusted proxy is configured or the peer is untrusted.
    """
    peer = request.client.host if request.client else None
    if peer and _is_trusted_proxy(peer):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",", 1)[0].strip() or peer
    return peer
