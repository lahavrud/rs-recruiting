"""Tests for the admin resume-view audit."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import Application, AuditLog, CandidateProfile
from rs_shared.services.admin.resume_access import audit_resume_view


async def _view_rows(session: AsyncSession) -> list[AuditLog]:
    rows = await session.execute(
        select(AuditLog).where(AuditLog.action == "candidate.resume_view")  # pyright: ignore[reportArgumentType]
    )
    return list(rows.scalars().all())


@pytest.mark.asyncio
async def test_view_of_profile_resume_is_audited_against_the_candidate(
    session: AsyncSession, candidate_profile: CandidateProfile
):
    candidate_profile.resume_path = "resumes/current.pdf"
    session.add(candidate_profile)
    await session.commit()

    await audit_resume_view(
        session, "current.pdf", actor_user_id=4, ip_address="203.0.113.7"
    )
    await session.commit()

    [row] = await _view_rows(session)
    assert (row.target_type, row.target_id) == (
        "CandidateProfile",
        candidate_profile.id,
    )
    assert (row.actor_user_id, row.ip_address, row.detail) == (4, "203.0.113.7", None)


@pytest.mark.asyncio
async def test_view_of_application_snapshot_names_the_application(
    session: AsyncSession, application: Application
):
    application.resume_path = "resumes/snapshot.pdf"
    session.add(application)
    await session.commit()

    await audit_resume_view(session, "snapshot.pdf", actor_user_id=4)
    await session.commit()

    [row] = await _view_rows(session)
    assert row.target_id == application.candidate_id
    assert row.detail == f"application_id={application.id}"


@pytest.mark.asyncio
async def test_view_of_file_without_owner_writes_nothing(session: AsyncSession):
    await audit_resume_view(session, "orphan.pdf", actor_user_id=4)
    await session.commit()

    assert await _view_rows(session) == []
