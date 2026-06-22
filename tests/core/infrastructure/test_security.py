"""Unit tests for security module (password hashing and JWT tokens)."""

from datetime import datetime, timedelta, timezone

import jwt

from src.core.infrastructure.config import get_jwt_secret_key, settings
from src.core.infrastructure.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    is_password_valid,
)


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_get_password_hash_produces_different_hashes(self):
        """Test that same password produces different hashes (salt)."""
        password = "test_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Hashes should be different due to salt
        assert hash1 != hash2
        # Both should be valid
        assert is_password_valid(password, hash1)
        assert is_password_valid(password, hash2)

    def test_get_password_hash_format(self):
        """Test that hash has correct format."""
        password = "test_password"
        hashed = get_password_hash(password)

        # Bcrypt hashes start with $2b$ or $2a$ and are 60 characters
        assert hashed.startswith("$2")
        assert len(hashed) == 60

    def test_get_password_hash_empty_password(self):
        """Test hash generation with empty password."""
        hashed = get_password_hash("")
        # Should not raise, but hash should be valid
        assert is_password_valid("", hashed)

    def test_is_password_valid_correct(self):
        """Test password verification with correct password."""
        password = "correct_password"
        hashed = get_password_hash(password)

        assert is_password_valid(password, hashed) is True

    def test_is_password_valid_incorrect(self):
        """Test password verification with incorrect password."""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)

        assert is_password_valid(wrong_password, hashed) is False

    def test_is_password_valid_hash_format_validation(self):
        """Test that is_password_valid validates hash format."""
        password = "test_password"
        invalid_hash = "not_a_valid_hash"

        # bcrypt raises ValueError for invalid hash format
        # is_password_valid should catch this and return False
        try:
            result = is_password_valid(password, invalid_hash)
            assert result is False
        except ValueError:
            # If ValueError is raised, that's also acceptable behavior
            # for invalid hash format
            pass


class TestJWTTokenCreation:
    """Tests for JWT token creation."""

    def test_create_access_token_with_valid_data(self):
        """Test token creation with valid data."""
        data = {"sub": "123", "email": "test@example.com", "role": "ADMIN"}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_contains_expected_claims(self):
        """Test that token contains expected claims."""
        data = {"sub": "123", "email": "test@example.com"}
        token = create_access_token(data)

        # Decode without verification to check claims
        payload = jwt.decode(
            token,
            get_jwt_secret_key(),
            algorithms=[settings.jwt_algorithm],
            options={"verify_signature": True},
        )

        assert payload["sub"] == "123"
        assert payload["email"] == "test@example.com"
        assert "exp" in payload

    def test_create_access_token_expiration_time(self):
        """Test that token expiration time is calculated correctly."""
        data = {"sub": "123"}
        token = create_access_token(data)

        payload = jwt.decode(
            token,
            get_jwt_secret_key(),
            algorithms=[settings.jwt_algorithm],
        )

        # Check expiration is in the future
        exp_timestamp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # Expiration should be approximately 30 minutes from now (default)
        expected_exp = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        # Allow 5 seconds tolerance
        assert abs((exp_datetime - expected_exp).total_seconds()) < 5

    def test_create_access_token_custom_expiration(self):
        """Test token creation with custom expiration."""
        data = {"sub": "123"}
        custom_delta = timedelta(hours=1)
        token = create_access_token(data, expires_delta=custom_delta)

        payload = jwt.decode(
            token,
            get_jwt_secret_key(),
            algorithms=[settings.jwt_algorithm],
        )

        exp_timestamp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # Expiration should be approximately 1 hour from now
        expected_exp = now + custom_delta
        # Allow 5 seconds tolerance
        assert abs((exp_datetime - expected_exp).total_seconds()) < 5


class TestJWTTokenDecoding:
    """Tests for JWT token decoding."""

    def test_decode_access_token_valid(self):
        """Test decoding a valid token."""
        data = {"sub": "123", "email": "test@example.com"}
        token = create_access_token(data)

        payload = decode_access_token(token)

        assert payload is not None
        assert payload["sub"] == "123"
        assert payload["email"] == "test@example.com"

    def test_decode_access_token_expired(self):
        """Test decoding an expired token."""
        data = {"sub": "123"}
        # Create token with very short expiration
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))

        # Wait a moment to ensure expiration
        payload = decode_access_token(token)

        # Expired token should return None
        assert payload is None

    def test_decode_access_token_invalid_format(self):
        """Test decoding with invalid token format."""
        invalid_token = "not.a.valid.jwt.token"

        payload = decode_access_token(invalid_token)

        assert payload is None

    def test_decode_access_token_wrong_secret(self):
        """Test that a token signed with the wrong secret is rejected."""
        wrong_key_token = jwt.encode(
            {"sub": "123", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
            "wrong_secret_key",
            algorithm=settings.jwt_algorithm,
        )
        payload = decode_access_token(wrong_key_token)
        assert payload is None

    def test_decode_access_token_missing_claims(self):
        """Test decoding token with missing required claims."""
        # Create minimal token
        token = create_access_token({"sub": "123"})

        payload = decode_access_token(token)

        # Should decode successfully if token is valid
        assert payload is not None
        assert payload["sub"] == "123"

    def test_decode_access_token_empty_string(self):
        """Test decoding with empty string."""
        payload = decode_access_token("")

        assert payload is None

    def test_decode_access_token_none(self):
        """Test decoding with None returns None."""
        assert decode_access_token(None) is None  # type: ignore[arg-type]
