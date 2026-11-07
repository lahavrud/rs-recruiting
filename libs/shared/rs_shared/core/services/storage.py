"""Storage abstraction layer — base class and provider factory."""

from abc import ABC, abstractmethod
from typing import Optional

from rs_shared.core.infrastructure.config import settings


class StorageProvider(ABC):
    """Abstract base class for storage providers."""

    @abstractmethod
    async def upload_file(
        self, file_content: bytes, file_name: str, content_type: Optional[str] = None
    ) -> str:
        """Upload a file and return its identifier/key."""
        pass

    @abstractmethod
    async def get_file_url(self, file_identifier: str) -> str:
        """Return a URL to access the file."""
        pass

    @abstractmethod
    async def download_file(self, file_identifier: str) -> bytes:
        """Download a file and return its raw bytes."""
        pass

    @abstractmethod
    async def delete_file(self, file_identifier: str) -> bool:
        """Delete a file; returns True even if it did not exist (idempotent)."""
        pass

    async def check_health(self) -> None:
        """Raise if the backing store is unreachable. Used by ``/health``.

        Default no-op so test doubles need not implement it; real providers
        override it with the cheapest call that proves access.
        """
        return None


def get_storage_provider() -> StorageProvider:
    """Factory: return the configured storage provider."""
    if settings.storage_provider == "s3":
        from rs_shared.core.services.storage_s3 import S3StorageProvider

        if not settings.aws_s3_bucket_name:
            raise ValueError("AWS_S3_BUCKET_NAME must be set when using S3 storage")
        return S3StorageProvider(
            bucket_name=settings.aws_s3_bucket_name,
            region=settings.aws_region,
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
            endpoint_url=settings.aws_s3_endpoint_url,
        )
    else:
        from rs_shared.core.services.storage_local import LocalStorageProvider

        return LocalStorageProvider(storage_path=settings.local_storage_path)
