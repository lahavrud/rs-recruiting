"""Unit tests for config module validation and parsing."""

import os
from unittest.mock import patch

import pytest

from rs_shared.core.infrastructure.config import (
    Settings,
    get_jwt_secret_key,
    validate_settings,
)


class TestValidateSettings:
    """Tests for validate_settings() function."""

    def test_validate_settings_valid_jwt_secret_key(self):
        """Test that valid JWT secret key passes validation."""
        with patch("rs_shared.core.infrastructure.config.settings") as mock_settings:
            mock_settings.testing = False
            mock_settings.jwt_secret_key = "a" * 32  # Valid 32+ char key

            # Should not raise
            validate_settings()

    def test_validate_settings_missing_jwt_secret_key(self):
        """Test that missing JWT secret key raises ValueError."""
        with patch("rs_shared.core.infrastructure.config.settings") as mock_settings:
            mock_settings.testing = False
            mock_settings.jwt_secret_key = None

            with pytest.raises(ValueError, match="JWT_SECRET_KEY must be set"):
                validate_settings()

    def test_validate_settings_short_jwt_secret_key(self):
        """Test that short JWT secret key (< 32 chars) raises ValueError."""
        with patch("rs_shared.core.infrastructure.config.settings") as mock_settings:
            mock_settings.testing = False
            mock_settings.jwt_secret_key = "short"  # Less than 32 chars

            with pytest.raises(ValueError, match="at least 32 characters"):
                validate_settings()

    def test_validate_settings_default_placeholder_jwt_secret_key(self):
        """Test that default/placeholder JWT secret key raises ValueError."""
        with patch("rs_shared.core.infrastructure.config.settings") as mock_settings:
            mock_settings.testing = False
            mock_settings.jwt_secret_key = "your-secret-key-change-in-production"

            with pytest.raises(ValueError, match="JWT_SECRET_KEY must be set"):
                validate_settings()

    @pytest.mark.parametrize("key", [None, "short"])
    def test_validate_settings_prod_requires_mfa_key(self, key):
        """Deployed envs must encrypt TOTP secrets with a real key (#1177)."""
        with patch("rs_shared.core.infrastructure.config.settings") as mock_settings:
            mock_settings.testing = False
            mock_settings.jwt_secret_key = "a" * 32
            mock_settings.environment = "prod"
            mock_settings.mfa_encryption_key = key

            with pytest.raises(ValueError, match="MFA_ENCRYPTION_KEY"):
                validate_settings()

    def test_validate_settings_prod_accepts_mfa_key(self):
        with patch("rs_shared.core.infrastructure.config.settings") as mock_settings:
            mock_settings.testing = False
            mock_settings.jwt_secret_key = "a" * 32
            mock_settings.environment = "prod"
            mock_settings.mfa_encryption_key = "m" * 64
            mock_settings.email_provider = "smtp"
            mock_settings.frontend_base_url = "https://rs-recruiting.com"

            validate_settings()

    def test_validate_settings_testing_mode_skips_validation(self):
        """Test that testing mode skips validation."""
        with patch("rs_shared.core.infrastructure.config.settings") as mock_settings:
            mock_settings.testing = True
            mock_settings.jwt_secret_key = None  # Invalid, but should be skipped

            # Should not raise when testing=True
            validate_settings()


class TestGetJWTSecretKey:
    """Tests for get_jwt_secret_key() function."""

    def test_get_jwt_secret_key_returns_secret_after_validation(self):
        """Test that get_jwt_secret_key returns secret key after validation."""
        with patch("rs_shared.core.infrastructure.config.settings") as mock_settings:
            mock_settings.jwt_secret_key = "a" * 32
            # Validate first
            validate_settings()

            secret = get_jwt_secret_key()
            assert secret == "a" * 32

    def test_get_jwt_secret_key_raises_assertion_error_if_not_validated(self):
        """Test that get_jwt_secret_key raises AssertionError if not validated."""
        with patch("rs_shared.core.infrastructure.config.settings") as mock_settings:
            mock_settings.jwt_secret_key = None

            # Should raise AssertionError if jwt_secret_key is None
            with pytest.raises(AssertionError, match="JWT_SECRET_KEY must be set"):
                get_jwt_secret_key()


class TestParseAllowedOrigins:
    """Tests for parse_allowed_origins() field validator."""

    def test_parse_allowed_origins_single_origin(self):
        """Test parsing single origin."""
        settings = Settings(allowed_origins="http://localhost:3000")
        assert settings.allowed_origins == ["http://localhost:3000"]

    def test_parse_allowed_origins_multiple_comma_separated(self):
        """Test parsing multiple comma-separated origins."""
        settings = Settings(
            allowed_origins="http://localhost:3000,http://localhost:3001,https://example.com"
        )
        assert settings.allowed_origins == [
            "http://localhost:3000",
            "http://localhost:3001",
            "https://example.com",
        ]

    def test_parse_allowed_origins_empty_string_uses_default(self):
        """Test that empty string uses default."""
        settings = Settings(allowed_origins="")
        assert settings.allowed_origins == ["http://localhost:3000"]

    def test_parse_allowed_origins_whitespace_trimming(self):
        """Test that whitespace is trimmed from origins."""
        settings = Settings(
            allowed_origins=" http://localhost:3000 , http://localhost:3001 "
        )
        assert settings.allowed_origins == [
            "http://localhost:3000",
            "http://localhost:3001",
        ]

    def test_parse_allowed_origins_default_fallback(self):
        """Test default fallback behavior."""
        # Test with whitespace-only string
        settings = Settings(allowed_origins="   ")
        assert settings.allowed_origins == ["http://localhost:3000"]

        # Test with None (should use default from Field)
        settings = Settings()
        assert settings.allowed_origins == ["http://localhost:3000"]

    def test_parse_allowed_origins_filters_empty_strings(self):
        """Test that empty strings in comma-separated list are filtered."""
        settings = Settings(
            allowed_origins="http://localhost:3000,,http://localhost:3001"
        )
        assert settings.allowed_origins == [
            "http://localhost:3000",
            "http://localhost:3001",
        ]

    def test_parse_allowed_origins_all_empty_fallback(self):
        """Test that all-empty origins list falls back to default."""
        settings = Settings(allowed_origins=", , ")
        assert settings.allowed_origins == ["http://localhost:3000"]


class TestSettingsInitialization:
    """Tests for Settings class initialization."""

    def test_settings_initialization_with_env_vars(self):
        """Test Settings initialization with environment variables."""
        with patch.dict(
            os.environ,
            {
                "JWT_SECRET_KEY": "test_secret_key_32_chars_long_!!",
                "DATABASE_URL": "postgresql+asyncpg://localhost/test",
            },
        ):
            settings = Settings()
            assert settings.jwt_secret_key == "test_secret_key_32_chars_long_!!"
            assert settings.database_url == "postgresql+asyncpg://localhost/test"

    def test_settings_initialization_defaults(self):
        """Test Settings initialization with defaults."""
        keys_to_clear = ["JWT_SECRET_KEY", "JWT_ACCESS_TOKEN_EXPIRE_MINUTES"]
        with patch.dict(os.environ, {}, clear=False):
            for k in keys_to_clear:
                os.environ.pop(k, None)
            settings = Settings()
            assert settings.jwt_algorithm == "HS256"
            assert settings.jwt_access_token_expire_minutes == 10
            assert settings.database_echo is False
            assert settings.testing is False
