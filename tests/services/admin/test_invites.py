"""Unit tests for admin_invites service layer."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.security import get_password_hash
from rs_shared.enums import InviteTokenStatus, UserRole
from rs_shared.models import InviteToken, User
from rs_shared.schemas import InviteTokenCreate
from rs_shared.services.admin.invites import (
    create_invite,
    delete_invite,
    list_invites,
    resend_invite,
    revoke_invite,
)
from rs_shared.services.exceptions import (
    EmailAlreadyExistsError,
    InviteAlreadyRevokedError,
    InviteNotFoundError,
    InvitePendingForEmailError,
)
from tests.conftest import audit_rows


async def _make_admin(session: AsyncSession) -> int:
    admin = User(
        email="inviteadmin@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    assert admin.id is not None
    return admin.id


def _invite_data(email: str) -> InviteTokenCreate:
    return InviteTokenCreate(email=email)


# ── create_invite ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_invite_success(session: AsyncSession):
    admin_id = await _make_admin(session)
    data = InviteTokenCreate(email="invite@example.com")
    result = await create_invite(admin_user_id=admin_id, data=data, session=session)
    await session.commit()

    assert result.email == "invite@example.com"
    assert result.status == InviteTokenStatus.PENDING

    db = (
        await session.execute(
            select(InviteToken).where(InviteToken.email == "invite@example.com")  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one()
    assert db.status == InviteTokenStatus.PENDING


@pytest.mark.asyncio
async def test_create_invite_duplicate_pending_raises(session: AsyncSession):
    admin_id = await _make_admin(session)
    data = _invite_data("dup@example.com")
    await create_invite(admin_user_id=admin_id, data=data, session=session)
    await session.commit()

    with pytest.raises(InvitePendingForEmailError):
        await create_invite(admin_user_id=admin_id, data=data, session=session)


@pytest.mark.asyncio
async def test_create_invite_existing_user_raises(session: AsyncSession):
    admin_id = await _make_admin(session)
    user = User(
        email="existing@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.commit()

    with pytest.raises(EmailAlreadyExistsError):
        await create_invite(
            admin_user_id=admin_id,
            data=_invite_data("existing@example.com"),
            session=session,
        )


# ── list_invites ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_invites_empty(session: AsyncSession):
    page = await list_invites(session)
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_list_invites_returns_all(session: AsyncSession):
    admin_id = await _make_admin(session)
    _exp = datetime(2099, 1, 1, tzinfo=timezone.utc)
    tokens = [("raw-aaa", "hash-aaa", _exp), ("raw-bbb", "hash-bbb", _exp)]
    with patch(
        "rs_shared.services.admin.invites.generate_invite_token",
        new_callable=AsyncMock,
        side_effect=tokens,
    ):
        for email in ["a@example.com", "b@example.com"]:
            await create_invite(
                admin_user_id=admin_id, data=_invite_data(email), session=session
            )
    await session.commit()

    page = await list_invites(session)
    assert len(page.items) == 2
    assert {i.email for i in page.items} == {"a@example.com", "b@example.com"}
    assert page.next_cursor is None


# ── revoke_invite ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_revoke_invite_success(session: AsyncSession):
    admin_id = await _make_admin(session)
    created = await create_invite(
        admin_user_id=admin_id, data=_invite_data("revoke@example.com"), session=session
    )
    await session.commit()

    await revoke_invite(
        created.id, session, actor_user_id=admin_id, ip_address="203.0.113.5"
    )
    await session.commit()

    db = (
        await session.execute(
            select(InviteToken).where(InviteToken.id == created.id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one()
    assert db.status == InviteTokenStatus.REVOKED
    [row] = await audit_rows("invite.revoke")
    assert (row.target_type, row.target_id) == ("invite", created.id)
    assert (row.actor_user_id, row.ip_address, row.detail) == (
        admin_id,
        "203.0.113.5",
        None,
    )


@pytest.mark.asyncio
async def test_delete_invite_leaves_an_audit_row(session: AsyncSession):
    """Once the invite is gone, its audit row is the only trace (no email in it)."""
    admin_id = await _make_admin(session)
    created = await create_invite(
        admin_user_id=admin_id, data=_invite_data("gone@example.com"), session=session
    )
    await session.commit()

    await delete_invite(created.id, session, actor_user_id=admin_id)
    await session.commit()

    assert await session.get(InviteToken, created.id) is None
    [row] = await audit_rows("invite.delete")
    assert (row.target_id, row.actor_user_id, row.detail) == (
        created.id,
        admin_id,
        None,
    )


@pytest.mark.asyncio
async def test_revoke_invite_not_found(session: AsyncSession):
    with pytest.raises(InviteNotFoundError):
        await revoke_invite(99999, session)


@pytest.mark.asyncio
async def test_revoke_invite_already_revoked_raises(session: AsyncSession):
    admin_id = await _make_admin(session)
    created = await create_invite(
        admin_user_id=admin_id,
        data=_invite_data("revoked2@example.com"),
        session=session,
    )
    await session.commit()

    await revoke_invite(created.id, session)
    await session.commit()

    with pytest.raises(InviteAlreadyRevokedError):
        await revoke_invite(created.id, session)


# ── resend_invite ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resend_invite_success(session: AsyncSession):
    admin_id = await _make_admin(session)
    _exp = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with patch(
        "rs_shared.services.admin.invites.generate_invite_token",
        new_callable=AsyncMock,
        side_effect=[
            ("original-raw", "original-hash", _exp),
            ("new-raw", "new-hash", _exp),
        ],
    ):
        created = await create_invite(
            admin_user_id=admin_id,
            data=_invite_data("resend@example.com"),
            session=session,
        )
        await session.commit()

        await resend_invite(created.id, session, actor_user_id=admin_id)
        await session.commit()

    db = (
        await session.execute(
            select(InviteToken).where(InviteToken.id == created.id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one()
    assert db.status == InviteTokenStatus.PENDING
    assert db.token_hash == "new-hash"
    [row] = await audit_rows("invite.resend")
    assert (row.target_id, row.actor_user_id) == (created.id, admin_id)


@pytest.mark.asyncio
async def test_resend_invite_not_found(session: AsyncSession):
    with pytest.raises(InviteNotFoundError):
        await resend_invite(99999, session)


@pytest.mark.asyncio
async def test_resend_used_invite_raises(session: AsyncSession):
    admin_id = await _make_admin(session)
    created = await create_invite(
        admin_user_id=admin_id, data=_invite_data("used@example.com"), session=session
    )
    await session.commit()

    db = (
        await session.execute(
            select(InviteToken).where(InviteToken.id == created.id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one()
    db.status = InviteTokenStatus.USED
    await session.commit()

    with pytest.raises(InviteAlreadyRevokedError):
        await resend_invite(created.id, session)
