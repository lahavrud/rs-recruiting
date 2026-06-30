"""Rate limiting configuration."""

from slowapi import Limiter

from rs_api.infrastructure.dependencies import client_ip as _client_ip
from rs_shared.core.infrastructure.config import settings


def _limiter_key(request) -> str:
    """Trusted-proxy-aware rate-limit key.

    Uses the same XFF extraction logic as the ``client_ip`` dependency so
    the limiter cannot be bypassed by spoofing ``X-Forwarded-For`` when the
    peer is not in ``TRUSTED_PROXY_IPS``.
    """
    return _client_ip(request) or "unknown"


def get_limiter() -> Limiter:
    """Get rate limiter instance.

    Disabled in testing mode and in local development; enabled in the deployed
    production and staging environments.
    """
    enabled = not settings.testing and settings.environment in (
        "prod",
        "staging",
    )
    return Limiter(
        key_func=_limiter_key,
        enabled=enabled,
    )


limiter = get_limiter()
