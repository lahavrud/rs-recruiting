"""Tests for admin notes on an application."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.enums import ApplicationStatus
from rs_shared.models import Application
from rs_shared.schemas import ApplicationRead
from rs_shared.services.admin.application_notes import update_application_notes
from rs_shared.services.exceptions import ApplicationNotFoundError
from tests.conftest import audit_rows


@pytest.mark.asyncio
async def test_update_application_notes_persists_text(
    session: AsyncSession, application: Application
):
    """Overwrites admin_notes without changing status."""
    result = await update_application_notes(
        application.id, "Looks promising — schedule call.", session
    )
    await session.commit()

    assert isinstance(result, ApplicationRead)
    assert result.admin_notes == "Looks promising — schedule call."
    assert result.status == ApplicationStatus.PENDING_ADMIN_REVIEW  # untouched


@pytest.mark.asyncio
async def test_update_application_notes_clears_to_none(
    session: AsyncSession, application: Application
):
    await update_application_notes(application.id, "first pass", session)
    await session.commit()
    cleared = await update_application_notes(application.id, None, session)
    await session.commit()
    assert cleared.admin_notes is None


@pytest.mark.asyncio
async def test_update_application_notes_not_found(session: AsyncSession):
    with pytest.raises(ApplicationNotFoundError):
        await update_application_notes(99999, "x", session)


@pytest.mark.asyncio
async def test_notes_edit_is_audited_without_the_text(
    session: AsyncSession, application: Application
):
    await update_application_notes(application.id, "private remark", session, 9)
    await session.commit()

    [row] = await audit_rows("application.notes_update")
    assert (row.target_type, row.target_id) == ("Application", application.id)
    assert (row.actor_user_id, row.detail) == (9, None)


@pytest.mark.asyncio
async def test_saving_unchanged_notes_writes_no_row(
    session: AsyncSession, application: Application
):
    await update_application_notes(application.id, None, session, 9)
    await session.commit()

    assert await audit_rows("application.notes_update") == []
