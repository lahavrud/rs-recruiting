"""Resume file validation + storage upload — shared by the apply flows.

A pure primitive over ``core.services`` (magic-byte validation + storage). Lives
in the kernel so both the public and candidate apply services use it without one
importing the other (see the ``independence`` import-linter contract).
"""

import hashlib

from rs_shared.core.services.file_validation import is_valid_document_magic_bytes
from rs_shared.core.services.storage import StorageProvider

_ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
_MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10 MB
_MIME_BY_EXT = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
}


async def validate_and_upload_resume(
    resume_file: bytes,
    resume_filename: str,
    storage: StorageProvider,
) -> tuple[str, str]:
    """Validate resume file (type, size, magic bytes) and upload it.

    Returns ``(storage_key, sha256_hex)``. Raises ``ValueError`` on any
    validation failure so callers can map the error consistently.
    """
    ext = resume_filename.lower().rsplit(".", 1)[-1] if "." in resume_filename else ""
    if f".{ext}" not in _ALLOWED_EXTENSIONS:
        raise ValueError(f"Invalid file type. Allowed: PDF, DOC, DOCX. Got: {ext}")
    if len(resume_file) > _MAX_RESUME_BYTES:
        raise ValueError(
            f"File size exceeds maximum of 10MB. Got: {len(resume_file)} bytes"
        )
    if not is_valid_document_magic_bytes(resume_file, ext):
        raise ValueError("Resume file content does not match the declared file type")

    content_type = _MIME_BY_EXT.get(ext, "application/octet-stream")
    storage_key = await storage.upload_file(
        file_content=resume_file,
        file_name=f"resumes/{resume_filename}",
        content_type=content_type,
    )
    return storage_key, hashlib.sha256(resume_file).hexdigest()
