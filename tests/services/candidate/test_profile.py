"""Service-level tests for candidate self-service profile (Sprint 11 / #608)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from rs_shared.models import CandidateProfile
from rs_shared.schemas import CandidateMeUpdate
from rs_shared.services.candidate.profile import (
    apply_identity_patch,
    remove_resume,
    replace_resume,
)

_PDF_BYTES = b"%PDF-1.4" + b"\x00" * 100


def _make_profile(**overrides) -> CandidateProfile:
    base = {
        "full_name": "Old Name",
        "email": "x@y.com",
        "phone": "050-000-0000",
        "linkedin_url": None,
        "resume_path": None,
    }
    base.update(overrides)
    return CandidateProfile(**base)


async def _run_post_commit_hooks() -> None:
    """Run what the service deferred, as transactional() does after its commit."""
    from rs_shared.core.infrastructure.transactions import _post_commit_hooks

    for hook in _post_commit_hooks.get() or []:
        await hook()


def _make_session() -> AsyncMock:
    session = AsyncMock()
    # ``add`` is synchronous on a real AsyncSession (the audit helper calls it).
    session.add = MagicMock()
    session.flush = AsyncMock(return_value=None)
    session.refresh = AsyncMock(return_value=None)
    return session


@pytest.mark.asyncio
async def test_apply_identity_patch_only_writes_set_fields():
    profile = _make_profile(linkedin_url="https://linkedin.com/in/old")
    await apply_identity_patch(
        profile,
        CandidateMeUpdate(full_name="New Name", phone="050-111-2222"),
        _make_session(),
    )
    assert profile.full_name == "New Name"
    assert profile.phone == "050-111-2222"
    # Omitted field is left alone, not nulled.
    assert profile.linkedin_url == "https://linkedin.com/in/old"


@pytest.mark.asyncio
async def test_apply_identity_patch_allows_clearing_linkedin():
    """linkedin_url is the one field where explicit-null clears the value.

    Passing ``linkedin_url=None`` in the patch is distinct from omitting
    the key — ``model_dump(exclude_unset=True)`` keeps explicitly-set
    fields, so this null reaches the writer and clears the column.
    """
    profile = _make_profile(linkedin_url="https://linkedin.com/in/old")
    await apply_identity_patch(
        profile, CandidateMeUpdate(linkedin_url=None), _make_session()
    )
    assert profile.linkedin_url is None


@pytest.mark.asyncio
async def test_apply_identity_patch_omitted_linkedin_preserves_existing():
    """When the patch leaves linkedin_url out entirely, the old value stays."""
    profile = _make_profile(linkedin_url="https://linkedin.com/in/keep")
    await apply_identity_patch(
        profile, CandidateMeUpdate(full_name="Updated Name"), _make_session()
    )
    assert profile.linkedin_url == "https://linkedin.com/in/keep"


@pytest.mark.asyncio
async def test_apply_identity_patch_clears_phone_on_explicit_null():
    """phone is nullable on the model — explicit null clears the value.

    Was rejecting null because only full_name + email are mandatory identity
    on the profile; phone is autofill metadata for the apply form and may
    be cleared. The apply-form endpoint enforces that a *new application*
    has a phone, regardless of what's on the profile.
    """
    profile = _make_profile(phone="050-111-2222")
    await apply_identity_patch(profile, CandidateMeUpdate(phone=None), _make_session())
    assert profile.phone is None


@pytest.mark.asyncio
async def test_apply_identity_patch_renames_resume_filename_with_same_extension():
    """Candidates can edit the display label, keeping the locked extension."""
    profile = _make_profile(
        resume_path="resumes/abc.pdf", resume_filename="Resume_v1.pdf"
    )
    await apply_identity_patch(
        profile, CandidateMeUpdate(resume_filename="Lahav_Resume.pdf"), _make_session()
    )
    assert profile.resume_filename == "Lahav_Resume.pdf"


@pytest.mark.asyncio
async def test_apply_identity_patch_rejects_resume_filename_extension_change():
    """The extension is locked to the bytes on disk — can't be renamed."""
    profile = _make_profile(resume_path="resumes/abc.pdf", resume_filename="Resume.pdf")
    with pytest.raises(ValueError, match="extension is locked"):
        await apply_identity_patch(
            profile, CandidateMeUpdate(resume_filename="Resume.docx"), _make_session()
        )


@pytest.mark.asyncio
async def test_apply_identity_patch_rejects_resume_filename_without_stored_resume():
    """Can't label a resume that doesn't exist."""
    profile = _make_profile(resume_path=None, resume_filename=None)
    with pytest.raises(ValueError, match="without a stored resume"):
        await apply_identity_patch(
            profile, CandidateMeUpdate(resume_filename="hello.pdf"), _make_session()
        )


@pytest.mark.asyncio
async def test_apply_identity_patch_clears_resume_filename_on_explicit_null():
    """Explicit-null clears the label — file on disk is unaffected."""
    profile = _make_profile(resume_path="resumes/abc.pdf", resume_filename="Resume.pdf")
    await apply_identity_patch(
        profile, CandidateMeUpdate(resume_filename=None), _make_session()
    )
    assert profile.resume_filename is None
    assert profile.resume_path == "resumes/abc.pdf"


@pytest.mark.asyncio
async def test_replace_resume_uploads_and_deletes_old_file():
    profile = _make_profile(resume_path="resumes/old.pdf")
    storage = AsyncMock()
    storage.upload_file = AsyncMock(return_value="resumes/new.pdf")
    storage.delete_file = AsyncMock(return_value=True)

    new_key = await replace_resume(
        profile, _PDF_BYTES, "new.pdf", "application/pdf", storage, _make_session()
    )

    assert new_key == "resumes/new.pdf"
    assert profile.resume_path == "resumes/new.pdf"
    # The user's original filename is captured as the display label.
    assert profile.resume_filename == "new.pdf"
    storage.upload_file.assert_awaited_once()
    # The old file goes only after the commit, so a rollback can't leave the
    # profile pointing at a deleted file.
    storage.delete_file.assert_not_called()
    await _run_post_commit_hooks()
    storage.delete_file.assert_awaited_once_with("resumes/old.pdf")


@pytest.mark.asyncio
async def test_replace_resume_first_upload_does_not_attempt_delete():
    profile = _make_profile(resume_path=None)
    storage = AsyncMock()
    storage.upload_file = AsyncMock(return_value="resumes/first.pdf")
    storage.delete_file = AsyncMock(return_value=True)

    await replace_resume(
        profile, _PDF_BYTES, "first.pdf", "application/pdf", storage, _make_session()
    )

    assert profile.resume_path == "resumes/first.pdf"
    storage.delete_file.assert_not_called()


@pytest.mark.asyncio
async def test_replace_resume_rejects_wrong_extension():
    profile = _make_profile()
    storage = AsyncMock()

    with pytest.raises(ValueError):
        await replace_resume(
            profile, _PDF_BYTES, "file.txt", "text/plain", storage, _make_session()
        )
    storage.upload_file.assert_not_called()


@pytest.mark.asyncio
async def test_replace_resume_rejects_oversize():
    profile = _make_profile()
    storage = AsyncMock()
    too_big = b"x" * (11 * 1024 * 1024)

    with pytest.raises(ValueError):
        await replace_resume(
            profile, too_big, "huge.pdf", "application/pdf", storage, _make_session()
        )


@pytest.mark.asyncio
async def test_replace_resume_rejects_bad_magic_bytes():
    profile = _make_profile()
    storage = AsyncMock()
    fake_pdf = b"NOT-A-REAL-PDF" + b"\x00" * 50

    with pytest.raises(ValueError):
        await replace_resume(
            profile, fake_pdf, "fake.pdf", "application/pdf", storage, _make_session()
        )


@pytest.mark.asyncio
async def test_replace_resume_storage_delete_failure_is_swallowed():
    """A failed cleanup of the old resume must not block the update."""
    profile = _make_profile(resume_path="resumes/old.pdf")
    storage = AsyncMock()
    storage.upload_file = AsyncMock(return_value="resumes/new.pdf")
    storage.delete_file = AsyncMock(side_effect=RuntimeError("storage down"))

    new_key = await replace_resume(
        profile, _PDF_BYTES, "new.pdf", "application/pdf", storage, _make_session()
    )
    assert new_key == "resumes/new.pdf"
    assert profile.resume_path == "resumes/new.pdf"


@pytest.mark.asyncio
async def test_remove_resume_idempotent_when_already_empty():
    profile = _make_profile(resume_path=None)
    storage = AsyncMock()

    await remove_resume(profile, storage, _make_session())
    assert profile.resume_path is None
    storage.delete_file.assert_not_called()


@pytest.mark.asyncio
async def test_remove_resume_clears_path_and_deletes_file():
    profile = _make_profile(resume_path="resumes/keep.pdf")
    storage = AsyncMock()
    storage.delete_file = AsyncMock(return_value=True)

    await remove_resume(profile, storage, _make_session())
    assert profile.resume_path is None
    storage.delete_file.assert_not_called()  # deferred until after commit
    await _run_post_commit_hooks()
    storage.delete_file.assert_awaited_once_with("resumes/keep.pdf")


def _audit_rows_added(session: AsyncMock) -> list:
    from rs_shared.models import AuditLog

    return [
        c.args[0] for c in session.add.call_args_list if isinstance(c.args[0], AuditLog)
    ]


@pytest.mark.asyncio
async def test_replace_resume_is_audited():
    profile = _make_profile(resume_path="resumes/old.pdf")
    profile.id = 7
    storage = AsyncMock()
    storage.upload_file = AsyncMock(return_value="resumes/new.pdf")
    storage.delete_file = AsyncMock(return_value=True)
    session = _make_session()

    await replace_resume(
        profile,
        _PDF_BYTES,
        "new.pdf",
        "application/pdf",
        storage,
        session,
        actor_user_id=3,
        ip_address="203.0.113.1",
    )

    [row] = _audit_rows_added(session)
    assert (row.action, row.target_type, row.target_id) == (
        "candidate.resume_replace",
        "CandidateProfile",
        7,
    )
    assert (row.actor_user_id, row.ip_address) == (3, "203.0.113.1")


@pytest.mark.asyncio
async def test_remove_resume_is_audited():
    profile = _make_profile(resume_path="resumes/old.pdf")
    profile.id = 7
    storage = AsyncMock()
    storage.delete_file = AsyncMock(return_value=True)
    session = _make_session()

    await remove_resume(profile, storage, session, actor_user_id=3)

    [row] = _audit_rows_added(session)
    assert (row.action, row.target_id, row.actor_user_id) == (
        "candidate.resume_remove",
        7,
        3,
    )


@pytest.mark.asyncio
async def test_remove_resume_without_a_resume_is_not_audited():
    """The endpoint is idempotent and unthrottled; a no-op must not write
    "resume removed" rows for a resume that never existed."""
    profile = _make_profile(resume_path=None)
    profile.id = 7
    session = _make_session()

    await remove_resume(profile, AsyncMock(), session, actor_user_id=3)

    assert _audit_rows_added(session) == []


@pytest.mark.asyncio
async def test_apply_identity_patch_audits_changed_field_names_only():
    profile = _make_profile(phone="050-000-0000")
    profile.id = 7
    session = _make_session()

    await apply_identity_patch(
        profile,
        CandidateMeUpdate(full_name="New Name", phone="050-000-0000"),
        session,
        actor_user_id=3,
        ip_address="203.0.113.9",
    )

    [row] = _audit_rows_added(session)
    assert (row.action, row.target_type, row.target_id) == (
        "candidate.profile_update",
        "CandidateProfile",
        7,
    )
    # phone was resent unchanged, so only full_name counts; no values stored.
    assert row.detail == "fields=full_name"
    assert (row.actor_user_id, row.ip_address) == (3, "203.0.113.9")


@pytest.mark.asyncio
async def test_apply_identity_patch_noop_is_not_audited():
    profile = _make_profile(full_name="Same")
    session = _make_session()

    await apply_identity_patch(profile, CandidateMeUpdate(full_name="Same"), session)

    assert _audit_rows_added(session) == []
