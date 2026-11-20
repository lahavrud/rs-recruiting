"""Tests for LocalStorageProvider, including path-traversal security."""

import tempfile
from pathlib import Path

import pytest

from rs_shared.core.services.storage_local import LocalStorageProvider


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


class TestLocalStorageProviderSecurity:
    """Security tests for LocalStorageProvider."""

    @pytest.fixture
    def provider(self, tmp_path):
        """Create a LocalStorageProvider instance with temp directory."""
        return LocalStorageProvider(storage_path=str(tmp_path))

    @pytest.mark.asyncio
    async def test_path_traversal_get_file_url(self, provider: LocalStorageProvider):
        """Test that path traversal is prevented in get_file_url."""
        with pytest.raises(ValueError, match="Path traversal"):
            await provider.get_file_url("../../../etc/passwd")

    @pytest.mark.asyncio
    async def test_path_traversal_delete_file(self, provider: LocalStorageProvider):
        """Test that path traversal is prevented in delete_file."""
        with pytest.raises(ValueError, match="Path traversal"):
            await provider.delete_file("../../../etc/passwd")

    @pytest.mark.asyncio
    async def test_path_traversal_multiple_levels(self, provider: LocalStorageProvider):
        """Test that multiple levels of path traversal are prevented."""
        with pytest.raises(ValueError, match="Path traversal"):
            await provider.get_file_url("../../../../../../etc/passwd")

    @pytest.mark.asyncio
    async def test_path_traversal_encoded(self, provider: LocalStorageProvider):
        """Test that URL-decoded traversal sequences are prevented."""
        import urllib.parse

        decoded = urllib.parse.unquote("%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd")
        with pytest.raises(ValueError, match="Path traversal"):
            await provider.get_file_url(decoded)

    @pytest.mark.asyncio
    async def test_valid_path_within_storage(self, provider: LocalStorageProvider):
        """Test that valid paths within storage directory work correctly."""
        # Upload a file
        file_content = b"test content"
        file_key = await provider.upload_file(file_content, "test.txt")

        # Should work fine
        url = await provider.get_file_url(file_key)
        assert url.startswith("/static/")

        # Delete should work
        result = await provider.delete_file(file_key)
        assert result is True

    @pytest.mark.asyncio
    async def test_file_with_double_dots_in_name(self, provider: LocalStorageProvider):
        """Test that files with '..' in the filename (not path traversal) work."""
        # Files like "test.txt.." or "file...." should be allowed
        # Even if the file_key contains ".." (e.g., from suffix extraction),
        # it should be accessible as long as it's not actual path traversal
        file_content = b"test content with dots"

        # Test file ending in ".." - upload and verify it works
        file_key1 = await provider.upload_file(file_content, "test.txt..")
        # Should be able to retrieve it (no path traversal error)
        url1 = await provider.get_file_url(file_key1)
        assert url1.startswith("/static/")

        # Should be able to delete it
        result1 = await provider.delete_file(file_key1)
        assert result1 is True

        # Test file with multiple dots
        file_key2 = await provider.upload_file(file_content, "file....")
        # Should be able to retrieve and delete without path traversal error
        url2 = await provider.get_file_url(file_key2)
        assert url2.startswith("/static/")
        result2 = await provider.delete_file(file_key2)
        assert result2 is True

        # Test file with ".." in the middle of the name
        file_key3 = await provider.upload_file(file_content, "file..name.txt")
        # Should work fine - ".." is part of filename, not path traversal
        url3 = await provider.get_file_url(file_key3)
        assert url3.startswith("/static/")
        result3 = await provider.delete_file(file_key3)
        assert result3 is True

        # Test that a file_key ending in ".." is accessible
        # This simulates the reported bug where files with ".." extension
        # become inaccessible
        # Create a file directly with a key ending in ".."
        # (simulating Path('test.txt..').suffix = "..")
        from uuid import uuid4

        test_key_with_dots = f"{uuid4()}.."
        test_file_path = provider.storage_path / test_key_with_dots
        test_file_path.write_bytes(file_content)

        # Should be able to access it (this was the bug - it was being blocked)
        url4 = await provider.get_file_url(test_key_with_dots)
        assert url4.startswith("/static/")

        # Should be able to delete it
        result4 = await provider.delete_file(test_key_with_dots)
        assert result4 is True

    @pytest.mark.asyncio
    async def test_path_traversal_still_blocked(self, provider: LocalStorageProvider):
        """Test that actual path traversal is still blocked."""
        with pytest.raises(ValueError, match="Path traversal"):
            await provider.get_file_url("../etc/passwd")

        with pytest.raises(ValueError, match="Path traversal"):
            await provider.get_file_url("../../secret.txt")

        with pytest.raises(ValueError, match="Path traversal"):
            await provider.delete_file("../etc/passwd")

    @pytest.mark.asyncio
    async def test_path_traversal_ending_with_dotdot(
        self, provider: LocalStorageProvider
    ):
        """A single '/..' resolves to storage_path root and is blocked.

        `subdir/..` resolves to storage_path itself — rel.parts is empty,
        so _safe_path raises before any filesystem call.  Deeper paths like
        `some/subdir/..` resolve to a subdirectory inside storage (not root)
        so they are not caught here; they fall through to the is_dir / not-found
        checks in the callers.
        """
        with pytest.raises(ValueError, match="Path traversal"):
            await provider.get_file_url("subdir/..")

        with pytest.raises(ValueError, match="Path traversal"):
            await provider.delete_file("subdir/..")

    @pytest.mark.asyncio
    async def test_valid_filenames_with_dots_still_work(
        self, provider: LocalStorageProvider
    ):
        """Test that valid filenames ending in '..' still work (not path traversal)."""
        file_content = b"test content"

        # Filename ending in ".." should work (no separator before dots)
        file_key1 = await provider.upload_file(file_content, "test..")
        url1 = await provider.get_file_url(file_key1)
        assert url1.startswith("/static/")
        await provider.delete_file(file_key1)

        # Filename with ".." in middle should work
        file_key2 = await provider.upload_file(file_content, "file..name.txt")
        url2 = await provider.get_file_url(file_key2)
        assert url2.startswith("/static/")
        await provider.delete_file(file_key2)

        # UUID with ".." extension should work
        from uuid import uuid4

        test_key = f"{uuid4()}.."
        test_file_path = provider.storage_path / test_key
        test_file_path.write_bytes(file_content)
        url3 = await provider.get_file_url(test_key)
        assert url3.startswith("/static/")
        await provider.delete_file(test_key)

    @pytest.mark.asyncio
    async def test_directory_path_blocked_in_get_file_url(
        self, provider: LocalStorageProvider
    ):
        """Test that get_file_url blocks directory paths."""
        subdir = provider.storage_path / "subdir"
        subdir.mkdir(exist_ok=True)

        # "subdir/.." resolves to storage_path itself — caught by the
        # not-rel.parts check in _safe_path before reaching is_dir().
        with pytest.raises(ValueError, match="Path traversal"):
            await provider.get_file_url("subdir/..")

    @pytest.mark.asyncio
    async def test_absolute_path_blocked(self, provider: LocalStorageProvider):
        """Absolute paths must be blocked — Path('/etc/passwd') escapes storage."""
        with pytest.raises(ValueError, match="Path traversal"):
            await provider.get_file_url("/etc/passwd")

        with pytest.raises(ValueError, match="Path traversal"):
            await provider.delete_file("/etc/passwd")

    @pytest.mark.asyncio
    async def test_symlink_to_outside_storage_is_rejected(
        self, provider: LocalStorageProvider
    ):
        """A symlink inside storage_path pointing OUTSIDE must be rejected.

        The resolve() + relative_to() check catches symlinks that escape the
        storage root without any string-level pre-filtering.

        Note: the symlink target must live OUTSIDE provider.storage_path.
        Using the provider fixture's own tmp_path here would make the
        target a sibling inside storage_path, and the relative_to check
        would (correctly) succeed.
        """
        with tempfile.TemporaryDirectory() as outside_root:
            outside_target = Path(outside_root) / "secret_target"
            outside_target.write_bytes(b"sensitive")

            link = provider.storage_path / "innocent_name"
            link.symlink_to(outside_target)

            with pytest.raises(ValueError, match="Path traversal"):
                await provider.get_file_url("innocent_name")

            with pytest.raises(ValueError, match="Path traversal"):
                await provider.delete_file("innocent_name")
