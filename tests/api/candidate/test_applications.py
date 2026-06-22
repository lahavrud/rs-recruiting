"""API tests for /api/candidate/me/applications endpoints (Sprint 11 / #609, #610)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_candidate, get_current_user
from src.core.infrastructure.security import get_password_hash
from src.enums import ApplicationStatus, JobStatus, UserRole
from src.main import app
from src.models import (
    Application,
    CandidateProfile,
    CompanyProfile,
    Job,
    User,
)
from tests.conftest import TestSessionLocal


async def _override_session():
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def _install_session_override():
    app.dependency_overrides[get_session] = _override_session
    yield
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_candidate, None)


def _override_user(user_id: int, email: str, role: UserRole = UserRole.CANDIDATE):
    async def _resolver() -> User:
        return User(
            id=user_id,
            email=email,
            hashed_password="x",  # pragma: allowlist secret
            role=role,
            is_active=True,
        )

    app.dependency_overrides[get_current_user] = _resolver


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_company_and_job(
    session: AsyncSession,
    *,
    company_name: str = "Acme",
    job_title: str = "Senior Engineer",
    job_status: JobStatus = JobStatus.PUBLISHED,
) -> tuple[CompanyProfile, Job]:
    owner = User(
        email=f"owner-{company_name.lower()}@test.com",
        hashed_password=get_password_hash("Secret1!"),  # pragma: allowlist secret
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(owner)
    await session.flush()
    company = CompanyProfile(
        user_id=owner.id,
        name=company_name,
        company_id="123456789",
        contact_email=owner.email,
        address="כתובת",
        contact_first_name="פרטי",
        contact_last_name="משפחה",
        contact_mobile_phone="0501234567",
    )
    session.add(company)
    await session.flush()
    job = Job(
        company_id=company.id,
        title=job_title,
        short_description="קצר",
        description="תיאור משרה ארוך",
        location="תל אביב",
        salary_min=20000,
        salary_max=30000,
        status=job_status,
    )
    session.add(job)
    await session.flush()
    return company, job


async def _seed_candidate(
    session: AsyncSession, email: str = "cand@test.com"
) -> tuple[User, CandidateProfile]:
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
        full_name="Cand Name",
        email=email,
        phone="050-000-0001",
    )
    session.add(profile)
    await session.commit()
    await session.refresh(user)
    await session.refresh(profile)
    return user, profile


async def _make_app(
    session: AsyncSession,
    *,
    candidate_id: int,
    job_id: int,
    status: ApplicationStatus = ApplicationStatus.NEW,
    resume_path: str | None = None,
    service_concept: str | None = "concept",
    salary_expectations: str | None = "30k",
    strength: str | None = "speed",
    growth_area: str | None = "depth",
) -> Application:
    a = Application(
        job_id=job_id,
        candidate_id=candidate_id,
        status=status,
        resume_path=resume_path,
        service_concept=service_concept,
        salary_expectations=salary_expectations,
        strength=strength,
        growth_area=growth_area,
    )
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a


# --------------------------------------------------------------------------
# GET /api/candidate/me/applications — list
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_returns_only_this_candidates_applications(test_db):
    async with TestSessionLocal() as session:
        _, j1 = await _seed_company_and_job(session, company_name="Mine")
        _, j2 = await _seed_company_and_job(session, company_name="Theirs")
        await session.commit()
        mine_user, mine_profile = await _seed_candidate(session, "mine@test.com")
        _, other_profile = await _seed_candidate(session, "other@test.com")
        await _make_app(session, candidate_id=mine_profile.id, job_id=j1.id)
        await _make_app(session, candidate_id=other_profile.id, job_id=j2.id)
    _override_user(mine_user.id, mine_user.email)

    async with await _client() as client:
        resp = await client.get("/api/candidate/me/applications")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["company"]["name"] == "Mine"


@pytest.mark.asyncio
async def test_list_excludes_withdrawn_rows(test_db):
    async with TestSessionLocal() as session:
        _, j_active = await _seed_company_and_job(session, company_name="Active")
        _, j_withdrawn = await _seed_company_and_job(session, company_name="Drawn")
        await session.commit()
        user, profile = await _seed_candidate(session, "wd@test.com")
        await _make_app(session, candidate_id=profile.id, job_id=j_active.id)
        await _make_app(
            session,
            candidate_id=profile.id,
            job_id=j_withdrawn.id,
            status=ApplicationStatus.WITHDRAWN,
        )
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.get("/api/candidate/me/applications")
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["company"]["name"] == "Active"


@pytest.mark.asyncio
async def test_list_row_shape_excludes_status_and_admin_notes(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "shape@test.com")
        await _make_app(session, candidate_id=profile.id, job_id=job.id)
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.get("/api/candidate/me/applications")
    row = resp.json()["items"][0]
    assert set(row.keys()) == {"id", "submitted_at", "editable", "job", "company"}
    assert set(row["job"].keys()) == {"id", "title", "closed"}
    assert set(row["company"].keys()) == {"id", "name"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,expected",
    [
        (ApplicationStatus.NEW, True),
        (ApplicationStatus.APPROVED_BY_ADMIN, False),
        (ApplicationStatus.REJECTED, False),
        (ApplicationStatus.HIRED, False),
    ],
)
async def test_list_editable_flag_maps_from_status(test_db, status, expected):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session, company_name=f"co-{status.value}")
        await session.commit()
        user, profile = await _seed_candidate(session, f"e-{status.value}@test.com")
        await _make_app(session, candidate_id=profile.id, job_id=job.id, status=status)
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.get("/api/candidate/me/applications")
    assert resp.json()["items"][0]["editable"] is expected


@pytest.mark.asyncio
async def test_list_pagination_cursor_walks_pages(test_db):
    async with TestSessionLocal() as session:
        # 25 distinct (company, job) pairs — the partial unique index blocks
        # multiple non-WITHDRAWN applications against the same job, so each
        # row needs its own job.
        jobs: list[Job] = []
        for i in range(25):
            _, j = await _seed_company_and_job(session, company_name=f"co-{i}")
            jobs.append(j)
        await session.commit()
        user, profile = await _seed_candidate(session, "page@test.com")
        for j in jobs:
            await _make_app(session, candidate_id=profile.id, job_id=j.id)
    _override_user(user.id, user.email)

    async with await _client() as client:
        first = (await client.get("/api/candidate/me/applications")).json()
        assert len(first["items"]) == 20
        assert first["next_cursor"]
        second = (
            await client.get(
                "/api/candidate/me/applications",
                params={"cursor": first["next_cursor"]},
            )
        ).json()
        assert len(second["items"]) == 5
        assert second["next_cursor"] is None


# --------------------------------------------------------------------------
# GET /api/candidate/me/applications/:id — detail
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detail_foreign_application_returns_404(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        mine_user, mine_profile = await _seed_candidate(session, "m@test.com")
        _, other_profile = await _seed_candidate(session, "o@test.com")
        other_app = await _make_app(
            session, candidate_id=other_profile.id, job_id=job.id
        )
    _override_user(mine_user.id, mine_user.email)

    async with await _client() as client:
        resp = await client.get(f"/api/candidate/me/applications/{other_app.id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_detail_withdrawn_returns_404(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "w@test.com")
        wd = await _make_app(
            session,
            candidate_id=profile.id,
            job_id=job.id,
            status=ApplicationStatus.WITHDRAWN,
        )
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.get(f"/api/candidate/me/applications/{wd.id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_detail_includes_my_answers_and_omits_status(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "d@test.com")
        a = await _make_app(
            session,
            candidate_id=profile.id,
            job_id=job.id,
            service_concept="פתרון",
            salary_expectations="25000",
            strength="חוזק",
            growth_area="צמיחה",
        )
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.get(f"/api/candidate/me/applications/{a.id}")
    body = resp.json()
    assert resp.status_code == 200
    assert "status" not in body
    assert "admin_notes" not in body
    assert body["my_answers"] == {
        "service_concept": "פתרון",
        "salary_expectations": "25000",
        "strength": "חוזק",
        "growth_area": "צמיחה",
    }
    assert body["job"]["description"] == "תיאור משרה ארוך"


@pytest.mark.asyncio
async def test_detail_job_closed_flag_reflects_current_job_status(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session, job_status=JobStatus.CLOSED)
        await session.commit()
        user, profile = await _seed_candidate(session, "c@test.com")
        a = await _make_app(session, candidate_id=profile.id, job_id=job.id)
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.get(f"/api/candidate/me/applications/{a.id}")
    assert resp.json()["job"]["closed"] is True


# --------------------------------------------------------------------------
# GET /api/candidate/me/applications/:id/resume — stream snapshot
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_streams_snapshot_bytes(test_db, tmp_path):
    # Configure local storage rooted at tmp_path so the FileResponse path
    # serves bytes from disk without hitting S3 or the real ./uploads dir.
    storage_root = tmp_path / "store"
    (storage_root / "resumes").mkdir(parents=True)
    file_basename = "snap123.pdf"
    (storage_root / "resumes" / file_basename).write_bytes(b"%PDF-1.4 test")

    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "r@test.com")
        a = await _make_app(
            session,
            candidate_id=profile.id,
            job_id=job.id,
            resume_path=f"resumes/{file_basename}",
        )
    _override_user(user.id, user.email)

    with (
        patch("src.api._resume_streaming.settings.storage_provider", "local"),
        patch(
            "src.api._resume_streaming.settings.local_storage_path", str(storage_root)
        ),
    ):
        async with await _client() as client:
            resp = await client.get(f"/api/candidate/me/applications/{a.id}/resume")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4 test"


@pytest.mark.asyncio
async def test_resume_returns_404_when_no_snapshot(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "n@test.com")
        a = await _make_app(
            session, candidate_id=profile.id, job_id=job.id, resume_path=None
        )
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.get(f"/api/candidate/me/applications/{a.id}/resume")
    assert resp.status_code == 404


# --------------------------------------------------------------------------
# Cascade + auth
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deleting_job_cascades_application_out_of_candidate_list(test_db):
    """Regression: Application.job_id has ON DELETE CASCADE, so removing a
    Job removes the application — and the candidate's list reflects that."""
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "cas@test.com")
        await _make_app(session, candidate_id=profile.id, job_id=job.id)
    _override_user(user.id, user.email)

    # Drop the job via raw delete (cascade fires at the DB level).
    async with TestSessionLocal() as session:
        await session.delete((await session.execute(select(Job))).scalar_one())
        await session.commit()

    async with await _client() as client:
        resp = await client.get("/api/candidate/me/applications")
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_endpoints_reject_non_candidate_roles(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "ok@test.com")
        a = await _make_app(session, candidate_id=profile.id, job_id=job.id)
    _override_user(99999, "admin@test.com", role=UserRole.ADMIN)

    async with await _client() as client:
        list_resp = await client.get("/api/candidate/me/applications")
        detail_resp = await client.get(f"/api/candidate/me/applications/{a.id}")
        resume_resp = await client.get(f"/api/candidate/me/applications/{a.id}/resume")
    for resp in (list_resp, detail_resp, resume_resp):
        assert resp.status_code == 403


# --------------------------------------------------------------------------
# PATCH /api/candidate/me/applications/:id — edit
# --------------------------------------------------------------------------

_MIN_PDF = (
    b"%PDF-1.4 1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
    b"0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n190\n%%EOF"
)


@pytest.mark.asyncio
async def test_patch_text_fields_on_new_application(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "pe1@test.com")
        a = await _make_app(
            session,
            candidate_id=profile.id,
            job_id=job.id,
            service_concept="old concept",
            strength="old strength",
        )
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.patch(
            f"/api/candidate/me/applications/{a.id}",
            data={"service_concept": "new concept", "strength": "new strength"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["my_answers"]["service_concept"] == "new concept"
    assert body["my_answers"]["strength"] == "new strength"
    assert "status" not in body
    assert "admin_notes" not in body


@pytest.mark.asyncio
async def test_patch_with_resume_replaces_snapshot(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "pe2@test.com")
        a = await _make_app(
            session,
            candidate_id=profile.id,
            job_id=job.id,
            resume_path="resumes/old.pdf",
        )
        old_profile_resume = profile.resume_path
    _override_user(user.id, user.email)

    deleted_keys: list[str] = []

    async def _fake_delete(key: str) -> bool:
        deleted_keys.append(key)
        return True

    mock_storage = MagicMock()
    mock_storage.delete_file = AsyncMock(side_effect=_fake_delete)

    with (
        patch(
            "src.services.candidate.applications.validate_and_upload_resume",
            return_value=("resumes/new.pdf", "abc123"),
        ),
        patch(
            "src.api.candidate.applications.get_storage_provider",
            return_value=mock_storage,
        ),
    ):
        async with await _client() as client:
            resp = await client.patch(
                f"/api/candidate/me/applications/{a.id}",
                files={"resume": ("new_cv.pdf", _MIN_PDF, "application/pdf")},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["resume"]["filename"] == "new_cv.pdf"
    assert deleted_keys == ["resumes/old.pdf"]

    async with TestSessionLocal() as session:
        refreshed_app = (
            await session.execute(select(Application).where(Application.id == a.id))
        ).scalar_one()
        assert refreshed_app.resume_path == "resumes/new.pdf"
        refreshed_profile = (
            await session.execute(
                select(CandidateProfile).where(CandidateProfile.id == profile.id)
            )
        ).scalar_one()
        assert refreshed_profile.resume_path == old_profile_resume


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        ApplicationStatus.APPROVED_BY_ADMIN,
        ApplicationStatus.REJECTED,
        ApplicationStatus.HIRED,
    ],
)
async def test_patch_on_non_new_status_returns_409(test_db, status):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session, company_name=f"co-{status.value}")
        await session.commit()
        user, profile = await _seed_candidate(session, f"pe3-{status.value}@test.com")
        a = await _make_app(
            session, candidate_id=profile.id, job_id=job.id, status=status
        )
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.patch(
            f"/api/candidate/me/applications/{a.id}",
            data={"service_concept": "irrelevant"},
        )
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"] == "application_not_editable"
    assert "status" not in str(body)


@pytest.mark.asyncio
async def test_patch_on_withdrawn_returns_404(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "pe4@test.com")
        a = await _make_app(
            session,
            candidate_id=profile.id,
            job_id=job.id,
            status=ApplicationStatus.WITHDRAWN,
        )
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.patch(
            f"/api/candidate/me/applications/{a.id}",
            data={"service_concept": "x"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_on_foreign_application_returns_404(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        mine_user, _ = await _seed_candidate(session, "pe5m@test.com")
        _, other_profile = await _seed_candidate(session, "pe5o@test.com")
        other_app = await _make_app(
            session, candidate_id=other_profile.id, job_id=job.id
        )
    _override_user(mine_user.id, mine_user.email)

    async with await _client() as client:
        resp = await client.patch(
            f"/api/candidate/me/applications/{other_app.id}",
            data={"service_concept": "x"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_empty_body_returns_400(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "pe6@test.com")
        a = await _make_app(session, candidate_id=profile.id, job_id=job.id)
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.patch(
            f"/api/candidate/me/applications/{a.id}",
            data={},
        )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "empty_body"


@pytest.mark.asyncio
async def test_patch_invalid_resume_mime_returns_400(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "pe7@test.com")
        a = await _make_app(
            session,
            candidate_id=profile.id,
            job_id=job.id,
            resume_path="resumes/orig.pdf",
        )
    _override_user(user.id, user.email)

    with patch(
        "src.core.services.file_validation.is_valid_document_magic_bytes",
        return_value=False,
    ):
        async with await _client() as client:
            resp = await client.patch(
                f"/api/candidate/me/applications/{a.id}",
                files={"resume": ("bad.pdf", b"not a real pdf", "application/pdf")},
            )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_resume"

    async with TestSessionLocal() as session:
        unchanged = (
            await session.execute(select(Application).where(Application.id == a.id))
        ).scalar_one()
        assert unchanged.resume_path == "resumes/orig.pdf"


@pytest.mark.asyncio
async def test_patch_resume_wrong_mime_returns_422(test_db):
    """PATCH resume with a non-PDF/DOCX MIME type is rejected at the API gate."""
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "pe8@test.com")
        a = await _make_app(
            session,
            candidate_id=profile.id,
            job_id=job.id,
            resume_path="resumes/orig.pdf",
        )
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.patch(
            f"/api/candidate/me/applications/{a.id}",
            files={"resume": ("cv.txt", b"plain text", "text/plain")},
        )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "unsupported_file_type"


@pytest.mark.asyncio
async def test_patch_resume_oversized_returns_413(test_db):
    """PATCH resume over 10 MB is rejected at the API gate with 413."""
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "pe9@test.com")
        a = await _make_app(
            session,
            candidate_id=profile.id,
            job_id=job.id,
            resume_path="resumes/orig.pdf",
        )
    _override_user(user.id, user.email)

    large_pdf = b"%PDF-1.4" + b"x" * (11 * 1024 * 1024)
    async with await _client() as client:
        resp = await client.patch(
            f"/api/candidate/me/applications/{a.id}",
            files={"resume": ("big.pdf", large_pdf, "application/pdf")},
        )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "file_too_large"


# --------------------------------------------------------------------------
# POST /api/candidate/me/applications/:id/withdraw
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_withdraw_on_new_sets_status_and_hides_from_list(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "wd1@test.com")
        a = await _make_app(session, candidate_id=profile.id, job_id=job.id)
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.post(f"/api/candidate/me/applications/{a.id}/withdraw")
        assert resp.status_code == 204

        list_resp = await client.get("/api/candidate/me/applications")
    assert list_resp.json()["items"] == []

    async with TestSessionLocal() as session:
        refreshed = (
            await session.execute(select(Application).where(Application.id == a.id))
        ).scalar_one()
        assert refreshed.status == ApplicationStatus.WITHDRAWN


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        ApplicationStatus.APPROVED_BY_ADMIN,
        ApplicationStatus.REJECTED,
        ApplicationStatus.HIRED,
    ],
)
async def test_withdraw_on_non_new_returns_409(test_db, status):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(
            session, company_name=f"wco-{status.value}"
        )
        await session.commit()
        user, profile = await _seed_candidate(session, f"wd2-{status.value}@test.com")
        a = await _make_app(
            session, candidate_id=profile.id, job_id=job.id, status=status
        )
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.post(f"/api/candidate/me/applications/{a.id}/withdraw")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "application_not_editable"


@pytest.mark.asyncio
async def test_withdraw_on_already_withdrawn_returns_404(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "wd3@test.com")
        a = await _make_app(
            session,
            candidate_id=profile.id,
            job_id=job.id,
            status=ApplicationStatus.WITHDRAWN,
        )
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.post(f"/api/candidate/me/applications/{a.id}/withdraw")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_withdraw_on_foreign_returns_404(test_db):
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        mine_user, _ = await _seed_candidate(session, "wd4m@test.com")
        _, other_profile = await _seed_candidate(session, "wd4o@test.com")
        other_app = await _make_app(
            session, candidate_id=other_profile.id, job_id=job.id
        )
    _override_user(mine_user.id, mine_user.email)

    async with await _client() as client:
        resp = await client.post(
            f"/api/candidate/me/applications/{other_app.id}/withdraw"
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_withdraw_allows_reapply_via_partial_unique_index(test_db):
    """After withdrawing, the candidate can submit a new application to the same job."""
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, "wd5@test.com")
        a = await _make_app(session, candidate_id=profile.id, job_id=job.id)
    _override_user(user.id, user.email)

    async with await _client() as client:
        withdraw = await client.post(f"/api/candidate/me/applications/{a.id}/withdraw")
        assert withdraw.status_code == 204

    async with TestSessionLocal() as session:
        second = Application(
            job_id=job.id,
            candidate_id=profile.id,
            status=ApplicationStatus.NEW,
        )
        session.add(second)
        await session.commit()
        await session.refresh(second)

    assert second.id != a.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field", ["service_concept", "salary_expectations", "strength", "growth_area"]
)
async def test_patch_text_field_over_2000_chars_returns_422(test_db, field: str):
    """PATCH rejects any text field exceeding 2000 characters with 422."""
    async with TestSessionLocal() as session:
        _, job = await _seed_company_and_job(session)
        await session.commit()
        user, profile = await _seed_candidate(session, f"big_{field}@test.com")
        a = await _make_app(session, candidate_id=profile.id, job_id=job.id)
    _override_user(user.id, user.email)

    async with await _client() as client:
        resp = await client.patch(
            f"/api/candidate/me/applications/{a.id}",
            data={field: "x" * 2001},
        )
    assert resp.status_code == 422
