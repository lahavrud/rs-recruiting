"""Local filesystem storage provider (development / testing)."""

import asyncio
import os
from pathlib import Path
from typing import Optional
from uuid import uuid4

from rs_shared.core.services.storage import StorageProvider


class LocalStorageProvider(StorageProvider):
    """Stores files on the local filesystem under a configurable directory."""

    _SUBDIRS = ("logos", "signatures", "contracts", "resumes")

    def __init__(self, storage_path: str = "./storage"):
        self.storage_path = Path(storage_path).resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        for subdir in self._SUBDIRS:
            (self.storage_path / subdir).mkdir(exist_ok=True)

    async def check_health(self) -> None:
        """The storage root must still exist and be writable."""
        if not os.access(self.storage_path, os.W_OK):
            raise OSError("local storage path is not writable")

    def _safe_path(self, file_identifier: str) -> Path:
        """Resolve and validate that the path stays strictly inside storage_path.

        Uses a single resolved-path containment check rather than fragile
        string matching — handles `../`, absolute paths, and symlinks uniformly.
        Raises ValueError for any identifier that resolves to storage_path itself
        (e.g. `subdir/..`) since callers expect a file, not the root directory.
        """
        resolved = (self.storage_path / file_identifier).resolve()
        try:
            rel = resolved.relative_to(self.storage_path)
        except ValueError:
            raise ValueError(
                f"Path traversal detected in identifier: {file_identifier!r}"
            )
        if not rel.parts:
            raise ValueError(
                f"Path traversal detected in identifier: {file_identifier!r}"
            )
        return resolved

    async def upload_file(
        self, file_content: bytes, file_name: str, content_type: Optional[str] = None
    ) -> str:
        parent = Path(file_name).parent
        suffix = Path(file_name).suffix
        if str(parent) != ".":
            file_key = f"{parent}/{uuid4()}{suffix}"
        else:
            file_key = f"{uuid4()}{suffix}"
        file_path = self._safe_path(file_key)  # raises ValueError on traversal
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, file_path.write_bytes, file_content)
        return file_key

    async def get_file_url(self, file_identifier: str) -> str:
        file_path = self._safe_path(file_identifier)
        loop = asyncio.get_event_loop()
        exists = await loop.run_in_executor(None, file_path.exists)
        if not exists:
            raise ValueError(f"File not found: {file_identifier}")
        if await loop.run_in_executor(None, file_path.is_dir):
            raise ValueError(f"Identifier is a directory: {file_identifier}")
        return f"/static/{file_identifier}"

    async def download_file(self, file_identifier: str) -> bytes:
        file_path = self._safe_path(file_identifier)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, file_path.read_bytes)

    async def delete_file(self, file_identifier: str) -> bool:
        file_path = self._safe_path(file_identifier)  # raises ValueError on traversal
        loop = asyncio.get_event_loop()
        try:
            exists = await loop.run_in_executor(None, file_path.exists)
            if exists:
                await loop.run_in_executor(None, file_path.unlink)
            return True
        except OSError:
            return False
