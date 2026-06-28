"""Unit tests for rate limiter module."""

from unittest.mock import MagicMock

from slowapi import Limiter

from src.core.infrastructure.config import settings
from src.core.infrastructure.limiter import _limiter_key, get_limiter


class TestGetLimiter:
    """Tests for get_limiter() function."""

    def test_get_limiter_creates_instance(self):
        """Test that limiter instance is created."""
        limiter = get_limiter()

        assert limiter is not None
        assert isinstance(limiter, Limiter)

    def test_get_limiter_configuration(self):
        """Test that limiter configuration is correct."""
        limiter = get_limiter()

        assert limiter._key_func is not None

    def test_key_func_is_limiter_key(self):
        """Limiter key function must be the trusted-proxy-aware variant."""
        limiter = get_limiter()

        assert limiter._key_func is _limiter_key


class TestLimiterKey:
    """Tests for _limiter_key() — the trusted-proxy-aware key extraction."""

    def _make_request(self, host: str, xff: str | None = None) -> MagicMock:
        req = MagicMock()
        req.client.host = host
        req.headers.get = lambda key, default=None: (
            xff if key == "x-forwarded-for" else default
        )
        return req

    def test_returns_peer_ip_when_not_a_trusted_proxy(self):
        """When the peer is not a trusted proxy, return request.client.host."""
        original = settings.trusted_proxy_ips
        try:
            settings.trusted_proxy_ips = ""
            req = self._make_request("1.2.3.4", xff="9.9.9.9")
            assert _limiter_key(req) == "1.2.3.4"
        finally:
            settings.trusted_proxy_ips = original

    def test_returns_xff_first_entry_for_trusted_proxy(self):
        """When the peer is a trusted proxy, read XFF and return its first entry."""
        original = settings.trusted_proxy_ips
        try:
            settings.trusted_proxy_ips = "172.28.0.0/24"
            req = self._make_request("172.28.0.2", xff="203.0.113.5, 1.1.1.1")
            assert _limiter_key(req) == "203.0.113.5"
        finally:
            settings.trusted_proxy_ips = original

    def test_returns_unknown_when_no_client(self):
        """Falls back to 'unknown' when request.client is None."""
        req = MagicMock()
        req.client = None
        assert _limiter_key(req) == "unknown"


class TestLimiterTestingMode:
    """Tests for rate limiter testing mode behavior."""

    def test_limiter_disabled_when_testing_true(self):
        """Test that rate limiting is disabled when settings.testing=True."""
        original_testing = settings.testing

        try:
            settings.testing = True
            limiter = get_limiter()

            assert limiter.enabled is False
        finally:
            settings.testing = original_testing

    def test_limiter_enabled_in_production(self):
        """Test that rate limiting is enabled only in production (non-testing)."""
        original_testing = settings.testing
        original_env = settings.environment

        try:
            settings.testing = False
            settings.environment = "production"
            limiter = get_limiter()
            assert limiter.enabled is True
        finally:
            settings.testing = original_testing
            settings.environment = original_env

    def test_limiter_disabled_in_development(self):
        """Test that rate limiting is disabled in development environment."""
        original_testing = settings.testing
        original_env = settings.environment

        try:
            settings.testing = False
            settings.environment = "development"
            limiter = get_limiter()
            assert limiter.enabled is False
        finally:
            settings.testing = original_testing
            settings.environment = original_env
