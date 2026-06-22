"""Tests for storage service."""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.infrastructure.config import settings
from src.core.services.storage import get_storage_provider
from src.core.services.storage_local import LocalStorageProvider
from src.core.services.storage_s3 import S3StorageProvider


class TestLocalStorageProvider:
    """Tests for LocalStorageProvider."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def provider(self, temp_dir):
        """Create a LocalStorageProvider instance."""
        return LocalStorageProvider(storage_path=temp_dir)

    @pytest.mark.asyncio
    async def test_upload_file_persists_with_uuid_key(
        self, provider: LocalStorageProvider
    ):
        """Test file upload."""
        file_content = b"test file content"
        file_name = "test.txt"

        file_key = await provider.upload_file(file_content, file_name)

        assert file_key is not None
        assert file_key.endswith(".txt")
        # Verify file exists
        file_path = provider.storage_path / file_key
        assert file_path.exists()
        assert file_path.read_bytes() == file_content

    @pytest.mark.asyncio
    async def test_get_file_url_returns_http_path(self, provider: LocalStorageProvider):
        """Test getting file URL."""
        file_content = b"test content"
        file_name = "test.txt"

        file_key = await provider.upload_file(file_content, file_name)
        url = await provider.get_file_url(file_key)

        assert url is not None
        # Should return HTTP URL path, not filesystem path
        assert url.startswith("/static/")
        assert file_key in url
        # Verify file exists on filesystem
        file_path = provider.storage_path / file_key
        assert file_path.exists()
        assert file_path.read_bytes() == file_content

    @pytest.mark.asyncio
    async def test_get_file_url_not_found(self, provider: LocalStorageProvider):
        """Test getting URL for non-existent file."""
        with pytest.raises(ValueError, match="File not found"):
            await provider.get_file_url("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_delete_file_removes_filesystem_entry(
        self, provider: LocalStorageProvider
    ):
        """Test file deletion."""
        file_content = b"test content"
        file_name = "test.txt"

        file_key = await provider.upload_file(file_content, file_name)
        file_path = provider.storage_path / file_key
        assert file_path.exists()

        result = await provider.delete_file(file_key)
        assert result is True
        assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, provider: LocalStorageProvider):
        """Test deleting non-existent file (idempotent - returns True)."""
        result = await provider.delete_file("nonexistent.txt")
        # Both S3 and Local providers return True for non-existent files (idempotent)
        assert result is True

    @pytest.mark.asyncio
    async def test_upload_with_content_type(self, provider: LocalStorageProvider):
        """Test file upload with content type."""
        file_content = b"<html><body>Test</body></html>"
        file_name = "test.html"

        file_key = await provider.upload_file(
            file_content, file_name, content_type="text/html"
        )

        assert file_key is not None
        assert file_key.endswith(".html")


class TestS3StorageProvider:
    """Tests for S3StorageProvider using AsyncMock (moto doesn't support aioboto3)."""

    # mock_s3_bucket fixture is now in conftest.py for reusability

    @pytest.mark.asyncio
    async def test_upload_file_delegates_to_s3_with_uuid_key(self, mock_s3_bucket):
        """Test S3 file upload using mocked S3 client."""

        provider = S3StorageProvider(
            bucket_name=mock_s3_bucket["bucket_name"],
            region=mock_s3_bucket["region"],
            access_key_id="test-key",
            secret_access_key="test-secret",
        )

        file_content = b"test file content"
        file_name = "test.txt"

        # Mock the S3 client
        mock_s3_client = AsyncMock()
        mock_s3_client.put_object = AsyncMock()

        with patch.object(provider.session, "client") as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_s3_client

            file_key = await provider.upload_file(file_content, file_name)
            assert file_key is not None
            assert file_key.endswith(".txt")

            # Verify put_object was called
            mock_s3_client.put_object.assert_called_once()
            call_kwargs = mock_s3_client.put_object.call_args[1]
            assert call_kwargs["Bucket"] == mock_s3_bucket["bucket_name"]
            assert call_kwargs["Body"] == file_content
            assert call_kwargs["ServerSideEncryption"] == "AES256"

    @pytest.mark.asyncio
    async def test_get_file_url_returns_s3_signed_url(self, mock_s3_bucket):
        """Test getting S3 presigned URL using mocked S3 client."""

        provider = S3StorageProvider(
            bucket_name=mock_s3_bucket["bucket_name"],
            region=mock_s3_bucket["region"],
            access_key_id="test-key",
            secret_access_key="test-secret",
        )

        file_key = "test-file-key.txt"
        expected_url = "https://test-bucket.s3.amazonaws.com/test-file-key.txt"

        # Mock the S3 client
        mock_s3_client = AsyncMock()
        mock_s3_client.generate_presigned_url = AsyncMock(return_value=expected_url)

        with patch.object(provider.session, "client") as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_s3_client

            url = await provider.get_file_url(file_key)

            assert url == expected_url
            mock_s3_client.generate_presigned_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_file_removes_s3_object(self, mock_s3_bucket):
        """delete_file permanently removes all versions and delete markers."""
        provider = S3StorageProvider(
            bucket_name=mock_s3_bucket["bucket_name"],
            region=mock_s3_bucket["region"],
            access_key_id="test-key",
            secret_access_key="test-secret",
        )
        file_key = "test-file-key.txt"

        # Async generator simulating one page with a version + a delete marker
        async def fake_paginate(**kwargs):
            yield {
                "Versions": [{"Key": file_key, "VersionId": "v1"}],
                "DeleteMarkers": [{"Key": file_key, "VersionId": "dm1"}],
            }

        mock_paginator = MagicMock()
        mock_paginator.paginate = fake_paginate

        mock_s3_client = AsyncMock()
        mock_s3_client.get_paginator = MagicMock(return_value=mock_paginator)
        mock_s3_client.delete_objects = AsyncMock(return_value={})

        with patch.object(provider.session, "client") as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_s3_client
            result = await provider.delete_file(file_key)

        assert result is True
        mock_s3_client.delete_objects.assert_called_once_with(
            Bucket=mock_s3_bucket["bucket_name"],
            Delete={
                "Objects": [
                    {"Key": file_key, "VersionId": "v1"},
                    {"Key": file_key, "VersionId": "dm1"},
                ],
                "Quiet": True,
            },
        )


class TestS3StorageProviderErrors:
    """Error-path tests: every ClientError is wrapped as ValueError."""

    @pytest.fixture
    def provider(self, mock_s3_bucket):
        return S3StorageProvider(
            bucket_name=mock_s3_bucket["bucket_name"],
            region=mock_s3_bucket["region"],
            access_key_id="test-key",
            secret_access_key="test-secret",
        )

    @staticmethod
    def _client_error(code: str, msg: str = "boom"):
        from botocore.exceptions import ClientError

        return ClientError({"Error": {"Code": code, "Message": msg}}, "Operation")

    @pytest.mark.asyncio
    async def test_upload_put_object_failure_raises_value_error(
        self, provider: S3StorageProvider
    ):
        mock_s3 = AsyncMock()
        mock_s3.put_object = AsyncMock(side_effect=self._client_error("AccessDenied"))

        with patch.object(provider.session, "client") as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_s3
            with pytest.raises(ValueError, match="Failed to upload file to S3"):
                await provider.upload_file(b"data", "file.txt")

    @pytest.mark.asyncio
    async def test_upload_verification_404_raises_specific_error(
        self, provider: S3StorageProvider
    ):
        """put_object succeeds but head_object 404 means the upload silently dropped."""

        mock_s3 = AsyncMock()
        mock_s3.put_object = AsyncMock()
        mock_s3.head_object = AsyncMock(side_effect=self._client_error("404"))

        with patch.object(provider.session, "client") as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_s3
            with pytest.raises(ValueError, match="object not found in S3 bucket"):
                await provider.upload_file(b"data", "file.txt")

    @pytest.mark.asyncio
    async def test_get_file_url_failure_raises_value_error(
        self, provider: S3StorageProvider
    ):
        mock_s3 = AsyncMock()
        mock_s3.generate_presigned_url = AsyncMock(
            side_effect=self._client_error("NoSuchKey")
        )

        with patch.object(provider.session, "client") as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_s3
            with pytest.raises(ValueError, match="Failed to generate URL"):
                await provider.get_file_url("missing-key.txt")

    @pytest.mark.asyncio
    async def test_download_file_failure_raises_value_error(
        self, provider: S3StorageProvider
    ):
        mock_s3 = AsyncMock()
        mock_s3.get_object = AsyncMock(side_effect=self._client_error("NoSuchKey"))

        with patch.object(provider.session, "client") as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_s3
            with pytest.raises(ValueError, match="Failed to download"):
                await provider.download_file("missing-key.txt")

    @pytest.mark.asyncio
    async def test_delete_file_failure_returns_false(self, provider: S3StorageProvider):
        """delete_file swallows ClientError and returns False (idempotent semantics)."""
        mock_s3 = AsyncMock()
        mock_s3.get_paginator = MagicMock(
            side_effect=self._client_error("AccessDenied")
        )

        with patch.object(provider.session, "client") as mock_client:
            mock_client.return_value.__aenter__.return_value = mock_s3
            assert await provider.delete_file("file.txt") is False


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
