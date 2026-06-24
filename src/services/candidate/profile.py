"""Candidate self-service profile + resume operations.

Single-row primitives for the authenticated candidate's own profile:
identity-field patches, resume replace (with storage cleanup of the
previous file), and resume removal. All callers must come through
``get_current_candidate`` — there's no admin override path here; admin
candidate edits live in ``src/services/admin/candidates.py``.
"""

from __future__ import annotations

import hashlib
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.storage_helpers import delete_file_best_effort
from src.core.infrastructure.transactions import defer_after_commit
from src.core.services.storage import StorageProvider
from src.models import CandidateProfile
from src.schemas import CandidateMeUpdate

logger = logging.getLogger(__name__)

_ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
_MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10 MB
_MIME_BY_EXT = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
}
_SAFE_FILENAME = re.compile(r"^[\w.\-]+$")
# Display-label cap. Must match ``CandidateMeUpdate.resume_filename``'s
# Pydantic max_length so an upload-captured name is never rejected by a
# subsequent PATCH that just submits the same value back.
_MAX_DISPLAY_FILENAME_LEN = 100


async def apply_identity_patch(
    profile: CandidateProfile, patch: CandidateMeUpdate, session: AsyncSession
) -> None:
    """Apply only the fields the candidate is allowed to change on themselves.

    Partial-update semantics: omitted keys leave the existing value alone.
    Email is NOT in the schema — the router rejects
    requests that try to include it.

    ``resume_filename`` is special: the candidate can rename the label
    but cannot change the file's extension (it must keep matching the
    bytes on disk under ``resume_path``). The extension is locked to
    the stored file's; raises ValueError on mismatch.
    """
    data = patch.model_dump(exclude_unset=True)
    if "full_name" in data and data["full_name"] is not None:
        profile.full_name = data["full_name"]
    # phone and linkedin_url are nullable on the model — explicit-null on the
    # patch clears the column (omitting the key leaves it alone).
    if "phone" in data:
        profile.phone = data["phone"]
    if "linkedin_url" in data:
        profile.linkedin_url = data["linkedin_url"]
    if "resume_filename" in data:
        profile.resume_filename = _resolve_renamed_filename(
            profile=profile, requested=data["resume_filename"]
        )
    await session.flush()
    await session.refresh(profile)


def _resolve_renamed_filename(
    *, profile: CandidateProfile, requested: str | None
) -> str | None:
    """Validate a resume-filename rename request.

    * Explicit null → clears the label (the file is still on disk).
    * No stored resume → reject; nothing to label.
    * Extension mismatch → reject; the bytes on disk have a fixed
      content type so the label's extension must match.
    """
    if requested is None:
        return None
    if not profile.resume_path:
        # Defensive: the UI shouldn't expose rename when there's no
        # resume, but reject loudly if it tries anyway.
        raise ValueError("Cannot set resume_filename without a stored resume")
    locked_ext = _extension_of(profile.resume_filename or profile.resume_path)
    new_ext = _extension_of(requested)
    if locked_ext.lower() != new_ext.lower():
        raise ValueError(
            "Resume filename extension is locked to the stored file"
            f" (expected .{locked_ext}, got .{new_ext})"
        )
    return requested


def _extension_of(name: str) -> str:
    """Bare extension (no dot) — empty string when none."""
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1]


def _truncate_display_filename(name: str) -> str:
    """Cap the display label at ``_MAX_DISPLAY_FILENAME_LEN`` chars while
    preserving the file extension. Long uploads still succeed; the
    label just gets the basename trimmed.

    ``Milano-...-Dark-Blue.docx`` (53 chars) is left alone, but a
    220-char filename would collapse to a 100-char display label that
    still ends with the real extension.
    """
    if len(name) <= _MAX_DISPLAY_FILENAME_LEN:
        return name
    if "." not in name:
        return name[:_MAX_DISPLAY_FILENAME_LEN]
    base, ext = name.rsplit(".", 1)
    suffix = "." + ext
    return base[: _MAX_DISPLAY_FILENAME_LEN - len(suffix)] + suffix


async def replace_resume(
    profile: CandidateProfile,
    content: bytes,
    filename: str,
    content_type: str | None,
    storage: StorageProvider,
    session: AsyncSession,
) -> str:
    """Replace the candidate's profile-level resume, deleting the prior file.

    Returns the new storage key. The Application snapshots are
    independent and not touched by this operation.

    Raises ``ValueError`` on validation failure (extension, magic bytes,
    size). The previous file is removed best-effort AFTER the new upload
    succeeds so a failed upload doesn't leave the candidate with no resume.
    """
    from src.core.services.file_validation import is_valid_document_magic_bytes

    if not filename or not _SAFE_FILENAME.match(filename.replace(" ", "_")):
        raise ValueError("Unsafe resume filename")

    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if f".{ext}" not in _ALLOWED_EXTENSIONS:
        raise ValueError("Invalid file type. Allowed: PDF, DOC, DOCX")
    if len(content) > _MAX_RESUME_BYTES:
        raise ValueError("File size exceeds 10MB limit")
    if not is_valid_document_magic_bytes(content, ext):
        raise ValueError("Resume file content does not match the declared file type")

    new_key = await storage.upload_file(
        file_content=content,
        file_name=f"resumes/{filename}",
        content_type=content_type or _MIME_BY_EXT.get(ext, "application/octet-stream"),
    )

    old_key = profile.resume_path
    profile.resume_path = new_key
    # Stash the candidate's original filename as the display label,
    # truncated to the policy cap so a 250-char filename can still
    # upload but the displayed label stays sane. They can rename it
    # later via PATCH (basename only — extension is locked).
    profile.resume_filename = _truncate_display_filename(filename)
    profile.resume_hash = hashlib.sha256(content).hexdigest()

    if old_key and old_key != new_key:
        # Best-effort cleanup — leaving a stale file behind is preferable
        # to blocking the candidate's update on a storage outage.
        await delete_file_best_effort(storage, old_key, logger)

    await session.flush()
    await session.refresh(profile)
    # Re-extract and re-embed the new resume, but only after the row is
    # committed (the worker reads it in a fresh session). Matching itself is
    # a live query at read time, so there's nothing else to recompute here.
    from src.core.tasks import enqueue_match_candidate_task

    candidate_id = profile.id
    if candidate_id is not None:
        defer_after_commit(lambda: enqueue_match_candidate_task(candidate_id))
    return new_key


async def remove_resume(
    profile: CandidateProfile, storage: StorageProvider, session: AsyncSession
) -> None:
    """Idempotent resume removal: delete the file (best-effort) + null the path.

    No-op when there is no resume on file. Application snapshots are untouched.
    Also clears the display label so a fresh upload starts clean.
    """
    old_key = profile.resume_path
    profile.resume_path = None
    profile.resume_filename = None
    profile.resume_hash = None
    # No resume → no basis for matching. Clear the derived data; matching
    # itself is a live query, so there are no persisted matches to clear.
    profile.parsed_text = None
    profile.embedding = None
    if old_key:
        await delete_file_best_effort(storage, old_key, logger, context="remove_resume")
    await session.flush()
    await session.refresh(profile)
