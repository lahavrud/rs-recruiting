"""Rate limiting configuration."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.infrastructure.config import settings


def get_limiter() -> Limiter:
    """Get rate limiter instance.

    Disabled in testing mode and in local development; enabled in the deployed
    production and staging environments.
    """
    enabled = not settings.testing and settings.environment in (
        "production",
        "staging",
    )
    return Limiter(
        key_func=get_remote_address,
        enabled=enabled,
    )


limiter = get_limiter()
