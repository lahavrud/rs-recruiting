"""Service-level tests for the candidate GDPR data export (Sprint 11 / #608)."""

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from rs_shared.core.infrastructure.security import get_password_hash
from rs_shared.enums import ApplicationStatus, UserRole
from rs_shared.models import (
    Application,
    AuditLog,
    CandidateProfile,
    DataExportRequest,
    Job,
    User,
)
from rs_shared.services.candidate.data_export import (
    DATA_EXPORT_TTL_HOURS,
    build_and_persist_export,
    has_pending_export,
)


async def _seed_candidate(
    session: AsyncSession, company_with_user, email: str = "exp@test.com"
) -> tuple[User, CandidateProfile, Job]:
    user = User(
        email=email,
        hashed_password=get_password_hash("Secret1!"),  # pragma: allowlist secret
        role=UserRole.CANDIDATE,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    profile = CandidateProfile(
        user_id=user.id,
        full_name="Export Me",
        email=email,
        phone="050-000-0001",
    )
    session.add(profile)
    await session.flush()

    job = Job(
        company_id=company_with_user.id,
        title="Senior Eng",
        short_description="role blurb",
        description="full",
        requirements=[{"text": "a"}, {"text": "b"}, {"text": "c"}],
        location="Tel Aviv",
        salary_min=10000,
        salary_max=20000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return user, profile, job


@pytest.mark.asyncio
async def test_has_pending_export_false_when_no_rows(
    session: AsyncSession, company_with_user
):
    user, _, _ = await _seed_candidate(
        session, company_with_user, "no-pending@test.com"
    )
    assert await has_pending_export(user.id, session) is False


@pytest.mark.asyncio
async def test_has_pending_export_true_when_unused_active(
    session: AsyncSession, company_with_user
):
    user, _, _ = await _seed_candidate(session, company_with_user, "active@test.com")
    session.add(
        DataExportRequest(
            token_hash="h",
            user_id=user.id,
            download_path="exports/x.zip",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    await session.commit()
    assert await has_pending_export(user.id, session) is True


@pytest.mark.asyncio
async def test_has_pending_export_false_when_used(
    session: AsyncSession, company_with_user
):
    user, _, _ = await _seed_candidate(session, company_with_user, "used@test.com")
    session.add(
        DataExportRequest(
            token_hash="h-used",
            user_id=user.id,
            download_path="exports/x.zip",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            used=True,
        )
    )
    await session.commit()
    assert await has_pending_export(user.id, session) is False


@pytest.mark.asyncio
async def test_has_pending_export_false_when_expired(
    session: AsyncSession, company_with_user
):
    user, _, _ = await _seed_candidate(session, company_with_user, "exp@test.com")
    session.add(
        DataExportRequest(
            token_hash="h-expired",
            user_id=user.id,
            download_path="exports/x.zip",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
    )
    await session.commit()
    assert await has_pending_export(user.id, session) is False


@pytest.mark.asyncio
async def test_build_and_persist_export_assembles_zip_and_persists_row(
    session: AsyncSession, company_with_user
):
    user, profile, job = await _seed_candidate(
        session, company_with_user, "build@test.com"
    )
    app = Application(
        job_id=job.id,
        candidate_id=profile.id,
        status=ApplicationStatus.NEW,
        service_concept="my service concept",
        salary_expectations="10-15k",
        resume_path="resumes/foo.pdf",
    )
    session.add(app)

    # Audit row attributable to this user — should appear in the export.
    session.add(
        AuditLog(
            actor_user_id=user.id,
            action="candidate_activated",
            target_type="User",
            target_id=user.id,
            detail="policy_version=1.2",
        )
    )
    await session.commit()

    # Real S3StorageProvider.upload_file ignores the requested basename and
    # mints its own uuid4 key, returning that actual key — the mock reflects
    # that by returning something other than the requested `file_name`, so
    # this test catches a regression back to persisting the requested name.
    actual_uploaded_key = f"exports/{user.id}/actually-written-key.zip"
    storage = AsyncMock()
    storage.upload_file = AsyncMock(return_value=actual_uploaded_key)
    storage.download_file = AsyncMock(return_value=b"%PDF-1.4 fake")

    raw_token, candidate_email = await build_and_persist_export(
        user.id, session, storage
    )
    await session.commit()

    assert candidate_email == "build@test.com"
    assert raw_token  # non-empty

    # ZIP was uploaded.
    storage.upload_file.assert_awaited_once()
    upload_kwargs = storage.upload_file.call_args.kwargs
    assert upload_kwargs["content_type"] == "application/zip"
    assert upload_kwargs["file_name"].startswith(f"exports/{user.id}/")

    # The bytes that were uploaded are a valid ZIP with data.json + the
    # resume file.
    zip_bytes = upload_kwargs["file_content"]
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        assert "data.json" in names
        assert any(n.startswith("resumes/") for n in names)
        payload = json.loads(zf.read("data.json"))

    assert payload["schema_version"] == "1.0"
    assert payload["user"]["email"] == "build@test.com"
    assert payload["profile"]["full_name"] == "Export Me"
    assert len(payload["applications"]) == 1
    assert payload["applications"][0]["service_concept"] == "my service concept"
    assert any(e["action"] == "candidate_activated" for e in payload["audit_log"])

    # DataExportRequest row exists with the expected TTL.
    record = (
        await session.execute(
            select(DataExportRequest).where(
                DataExportRequest.user_id == user.id  # type: ignore[arg-type]
            )
        )
    ).scalar_one()
    assert record.used is False
    delta = record.expires_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
    assert abs(delta.total_seconds() - DATA_EXPORT_TTL_HOURS * 3600) < 60

    # Regression guard: download_path must be the key upload_file actually
    # wrote to, NOT the name we requested — they legitimately differ because
    # upload_file mints its own uuid4 basename.
    assert record.download_path == actual_uploaded_key
    assert record.download_path != upload_kwargs["file_name"]


@pytest.mark.asyncio
async def test_build_export_continues_when_a_resume_fetch_fails(
    session: AsyncSession, company_with_user
):
    """Partial storage failure on one resume must not abort the whole export."""
    user, profile, job = await _seed_candidate(
        session, company_with_user, "partial@test.com"
    )
    app1 = Application(
        job_id=job.id,
        candidate_id=profile.id,
        status=ApplicationStatus.NEW,
        resume_path="resumes/missing.pdf",
    )
    session.add(app1)
    await session.commit()

    storage = AsyncMock()
    storage.upload_file = AsyncMock(
        return_value=f"exports/{user.id}/actually-written-key.zip"
    )
    storage.download_file = AsyncMock(side_effect=RuntimeError("S3 timeout"))

    raw_token, _ = await build_and_persist_export(user.id, session, storage)
    await session.commit()
    assert raw_token  # still produced

    upload_kwargs = storage.upload_file.call_args.kwargs
    with zipfile.ZipFile(io.BytesIO(upload_kwargs["file_content"])) as zf:
        # data.json present, missing resume omitted (not aborted).
        assert "data.json" in zf.namelist()
        assert not any(n.startswith("resumes/") for n in zf.namelist())
