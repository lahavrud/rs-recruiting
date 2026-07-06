"""Service-layer tests for src/services/candidate/applications.py (Sprint 11 / #609)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import get_password_hash
from rs_shared.enums import ApplicationStatus, JobStatus, UserRole
from rs_shared.models import Application, CandidateProfile, CompanyProfile, Job, User
from rs_shared.services.candidate.applications import (
    get_application_resume_key,
    get_my_application,
    list_my_applications,
)
from rs_shared.services.exceptions import ApplicationNotFoundError, InvalidCursorError
from tests.conftest import TestSessionLocal


async def _company_and_job(
    session: AsyncSession,
    *,
    company_name: str = "Acme",
    job_status: JobStatus = JobStatus.PUBLISHED,
) -> Job:
    owner = User(
        email=f"o-{company_name}@t.com",
        hashed_password=get_password_hash("S1!"),  # pragma: allowlist secret
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(owner)
    await session.flush()
    company = CompanyProfile(
        user_id=owner.id,
        name=company_name,
        company_id="111111111",
        contact_email=owner.email,
        contact_first_name="פ",
        contact_last_name="מ",
        contact_mobile_phone="0501112222",
        address="כתובת",
    )
    session.add(company)
    await session.flush()
    job = Job(
        company_id=company.id,
        title=f"Job {company_name}",
        short_description="קצר",
        description="ארוך",
        location="ת״א",
        salary_min=10000,
        salary_max=20000,
        status=job_status,
    )
    session.add(job)
    await session.flush()
    return job


async def _candidate(session: AsyncSession, email: str) -> CandidateProfile:
    u = User(
        email=email,
        hashed_password=get_password_hash("S1!"),  # pragma: allowlist secret
        role=UserRole.CANDIDATE,
        is_active=True,
    )
    session.add(u)
    await session.flush()
    p = CandidateProfile(
        user_id=u.id,
        full_name="Name",
        email=email,
        phone="050-000-0001",
    )
    session.add(p)
    await session.flush()
    return p


async def _app(
    session: AsyncSession,
    *,
    candidate_id: int,
    job_id: int,
    status: ApplicationStatus = ApplicationStatus.NEW,
    resume_path: str | None = None,
) -> Application:
    a = Application(
        job_id=job_id,
        candidate_id=candidate_id,
        status=status,
        resume_path=resume_path,
    )
    session.add(a)
    await session.flush()
    return a


@pytest.mark.asyncio
async def test_list_filters_to_owner_and_excludes_withdrawn(test_db):
    async with TestSessionLocal() as session:
        j_a = await _company_and_job(session, company_name="A")
        j_b = await _company_and_job(session, company_name="B")
        j_c = await _company_and_job(session, company_name="C")
        cand = await _candidate(session, "c@test.com")
        other = await _candidate(session, "o@test.com")
        await _app(session, candidate_id=cand.id, job_id=j_a.id)
        await _app(
            session,
            candidate_id=cand.id,
            job_id=j_b.id,
            status=ApplicationStatus.WITHDRAWN,
        )
        await _app(session, candidate_id=other.id, job_id=j_c.id)
        await session.commit()

        page = await list_my_applications(session, candidate_id=cand.id)
    assert {item.job.title for item in page.items} == {"Job A"}
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_list_pagination_emits_next_cursor_when_page_full(test_db):
    async with TestSessionLocal() as session:
        cand = await _candidate(session, "p@test.com")
        for i in range(5):
            j = await _company_and_job(session, company_name=f"co-{i}")
            await _app(session, candidate_id=cand.id, job_id=j.id)
        await session.commit()

        page1 = await list_my_applications(session, candidate_id=cand.id, limit=3)
        assert len(page1.items) == 3
        assert page1.next_cursor is not None
        page2 = await list_my_applications(
            session, candidate_id=cand.id, limit=3, cursor=page1.next_cursor
        )
    assert len(page2.items) == 2
    assert page2.next_cursor is None


@pytest.mark.asyncio
async def test_list_invalid_cursor_raises(test_db):
    async with TestSessionLocal() as session:
        cand = await _candidate(session, "ic@test.com")
        await session.commit()
        with pytest.raises(InvalidCursorError):
            await list_my_applications(
                session, candidate_id=cand.id, cursor="not-a-real-cursor"
            )


@pytest.mark.asyncio
async def test_get_my_application_projects_detail_with_editable_flag(test_db):
    async with TestSessionLocal() as session:
        j = await _company_and_job(session)
        cand = await _candidate(session, "d@test.com")
        a = await _app(session, candidate_id=cand.id, job_id=j.id)
        await session.commit()

        detail = await get_my_application(
            session, candidate_id=cand.id, application_id=a.id
        )
    assert detail.editable is True
    assert detail.job.closed is False
    assert detail.my_answers.service_concept is None


@pytest.mark.asyncio
async def test_get_my_application_404_when_withdrawn(test_db):
    async with TestSessionLocal() as session:
        j = await _company_and_job(session)
        cand = await _candidate(session, "wd@test.com")
        a = await _app(
            session,
            candidate_id=cand.id,
            job_id=j.id,
            status=ApplicationStatus.WITHDRAWN,
        )
        await session.commit()

        with pytest.raises(ApplicationNotFoundError):
            await get_my_application(session, candidate_id=cand.id, application_id=a.id)


@pytest.mark.asyncio
async def test_get_my_application_404_when_foreign(test_db):
    async with TestSessionLocal() as session:
        j = await _company_and_job(session)
        owner = await _candidate(session, "owner@test.com")
        outsider = await _candidate(session, "outsider@test.com")
        a = await _app(session, candidate_id=owner.id, job_id=j.id)
        await session.commit()

        with pytest.raises(ApplicationNotFoundError):
            await get_my_application(
                session, candidate_id=outsider.id, application_id=a.id
            )


@pytest.mark.asyncio
async def test_get_application_resume_key_returns_stored_path(test_db):
    async with TestSessionLocal() as session:
        j = await _company_and_job(session)
        cand = await _candidate(session, "rk@test.com")
        a = await _app(
            session,
            candidate_id=cand.id,
            job_id=j.id,
            resume_path="resumes/abc.pdf",
        )
        await session.commit()

        key = await get_application_resume_key(
            session, candidate_id=cand.id, application_id=a.id
        )
    assert key == "resumes/abc.pdf"


@pytest.mark.asyncio
async def test_get_application_resume_key_404_when_no_snapshot(test_db):
    async with TestSessionLocal() as session:
        j = await _company_and_job(session)
        cand = await _candidate(session, "ns@test.com")
        a = await _app(session, candidate_id=cand.id, job_id=j.id, resume_path=None)
        await session.commit()

        with pytest.raises(ApplicationNotFoundError):
            await get_application_resume_key(
                session, candidate_id=cand.id, application_id=a.id
            )
