"""Security utilities for password hashing and JWT tokens."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from jwt import InvalidTokenError

from rs_shared.core.infrastructure.config import get_jwt_secret_key, settings

# bcrypt only uses the first 72 bytes of a password, and bcrypt>=5 raises
# ValueError instead of truncating. Registration rejects longer passwords
# (`_validate_password_complexity`), so no stored hash can come from one.
BCRYPT_MAX_PASSWORD_BYTES = 72


def is_password_valid(plain_password: str, hashed_password: str) -> bool:
    """Check a password against a bcrypt hash; never raises on long input.

    A password over 72 bytes can't match any hash we issued, but it still runs
    a full ``checkpw`` (on the first 72 bytes) so its response takes the same
    time as any other wrong password, and the result is always ``False``.
    """
    password_bytes = plain_password.encode("utf-8")
    too_long = len(password_bytes) > BCRYPT_MAX_PASSWORD_BYTES
    matched = bcrypt.checkpw(
        password_bytes[:BCRYPT_MAX_PASSWORD_BYTES],
        hashed_password.encode("utf-8"),
    )
    return matched and not too_long


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def hash_token(token: str) -> str:
    """SHA-256 hash a token for safe DB storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode["iat"] = now
    to_encode["exp"] = expire
    return jwt.encode(to_encode, get_jwt_secret_key(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token, get_jwt_secret_key(), algorithms=[settings.jwt_algorithm]
        )
    except InvalidTokenError:
        return None


_REFRESH_TTL_SHORT = timedelta(days=1)  # remember_me=False (session-like)
# Exported — imported by login.py to derive the cookie max_age.
REFRESH_TTL_LONG = timedelta(days=30)  # remember_me=True


def create_refresh_token(*, remember_me: bool = False) -> tuple[str, str, datetime]:
    """Generate a cryptographically secure refresh token.

    Returns:
        (raw_token, hashed_token, expires_at)
    """
    import secrets

    raw = secrets.token_urlsafe(48)
    ttl = REFRESH_TTL_LONG if remember_me else _REFRESH_TTL_SHORT
    expires_at = datetime.now(timezone.utc) + ttl
    return raw, hash_token(raw), expires_at
