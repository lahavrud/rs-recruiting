"""Tests for the storage provider factory and health checks."""

import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.services.storage import get_storage_provider
from rs_shared.core.services.storage_local import LocalStorageProvider
from rs_shared.core.services.storage_s3 import S3StorageProvider


class TestStorageHealthChecks:
    """check_health() backs the /health endpoint's storage check."""

    @pytest.mark.asyncio
    async def test_local_check_passes_for_writable_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            await LocalStorageProvider(storage_path=tmpdir).check_health()

    @pytest.mark.asyncio
    async def test_local_check_raises_when_root_is_gone(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = LocalStorageProvider(storage_path=tmpdir)
        with pytest.raises(OSError):
            await provider.check_health()

    @pytest.mark.asyncio
    async def test_s3_check_heads_the_configured_bucket(self):
        provider = S3StorageProvider(bucket_name="rs-bucket", region="us-east-1")
        mock_s3 = AsyncMock()

        with patch.object(provider.session, "client") as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_s3
            await provider.check_health()

        mock_s3.head_bucket.assert_awaited_once_with(Bucket="rs-bucket")

    @pytest.mark.asyncio
    async def test_s3_check_propagates_access_errors(self):
        from botocore.exceptions import ClientError

        provider = S3StorageProvider(bucket_name="rs-bucket", region="us-east-1")
        mock_s3 = AsyncMock()
        mock_s3.head_bucket = AsyncMock(
            side_effect=ClientError({"Error": {"Code": "403"}}, "HeadBucket")
        )

        with patch.object(provider.session, "client") as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_s3
            with pytest.raises(ClientError):
                await provider.check_health()


class TestStorageProviderFactory:
    """Tests for storage provider factory function."""

    def test_get_storage_provider_local(self, monkeypatch):
        """Test getting local storage provider."""
        monkeypatch.setattr(settings, "storage_provider", "local")
        monkeypatch.setattr(settings, "local_storage_path", "./test_storage")

        provider = get_storage_provider()
        assert isinstance(provider, LocalStorageProvider)
        # storage_path is now resolved to absolute path
        assert provider.storage_path.is_absolute()
        assert "test_storage" in str(provider.storage_path)

    def test_get_storage_provider_s3(self, monkeypatch):
        """Test getting S3 storage provider."""
        monkeypatch.setattr(settings, "storage_provider", "s3")
        monkeypatch.setattr(settings, "aws_s3_bucket_name", "test-bucket")
        monkeypatch.setattr(settings, "aws_region", "us-east-1")

        provider = get_storage_provider()
        assert isinstance(provider, S3StorageProvider)
        assert provider.bucket_name == "test-bucket"

    def test_get_storage_provider_s3_missing_bucket(self, monkeypatch):
        """Test S3 provider requires bucket name."""
        monkeypatch.setattr(settings, "storage_provider", "s3")
        monkeypatch.setattr(settings, "aws_s3_bucket_name", None)

        with pytest.raises(ValueError, match="AWS_S3_BUCKET_NAME must be set"):
            get_storage_provider()
