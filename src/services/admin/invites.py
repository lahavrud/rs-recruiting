"""Admin service layer for invite token management."""

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.invite_tokens import generate_invite_token
from src.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.core.infrastructure.transactions import defer_after_commit
from src.core.tasks import enqueue_email_task
from src.enums import InviteTokenStatus
from src.models import InviteToken, User
from src.schemas import InviteTokenCreate, InviteTokenRead
from src.services.exceptions import (
    EmailAlreadyExistsError,
    InviteAlreadyRevokedError,
    InviteNotFoundError,
    InvitePendingForEmailError,
)
from src.services.utils.audit import record_audit_event
from src.templates.email import build_invite_html


async def _send_invite_email(email: str, registration_url: str) -> None:
    plain = (
        f"הוזמנת להירשם לפלטפורמת RS Recruiting.\n\n"
        f"לחצו על הקישור הבא להשלמת תהליך ההרשמה:\n{registration_url}\n\n"
        "שימו לב: הקישור תקף לשעתיים בלבד.\n\nבברכה,\nצוות RS Recruiting"
    )
    html = build_invite_html(registration_url)
    await enqueue_email_task(
        to=email,
        subject="הזמנה להרשמה ל-RS Recruiting",
        body=plain,
        html_body=html,
    )


async def create_invite(
    admin_user_id: int,
    data: InviteTokenCreate,
    session: AsyncSession,
) -> InviteTokenRead:
    """Generate a token, store metadata in DB, send invite email."""
    normalized_email = data.email.lower().strip()
    existing_user = await session.execute(
        select(User).where(User.email == normalized_email)  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
    )
    if existing_user.scalar_one_or_none() is not None:
        raise EmailAlreadyExistsError(normalized_email)

    pending_invite = await session.execute(
        select(InviteToken).where(
            InviteToken.email == data.email,
            InviteToken.status == InviteTokenStatus.PENDING,  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
        )
    )
    if pending_invite.scalar_one_or_none() is not None:
        raise InvitePendingForEmailError(data.email)

    raw_token, token_hash, expires_at = await generate_invite_token()

    record = InviteToken(
        token_hash=token_hash,
        email=data.email,
        status=InviteTokenStatus.PENDING,
        created_by_admin_id=admin_user_id,
        expires_at=expires_at,
    )
    session.add(record)
    await session.flush()

    await record_audit_event(
        session,
        actor_user_id=admin_user_id,
        action="invite_created",
        target_type="invite",
        target_id=record.id,
        detail=data.email,
    )

    _email = data.email
    registration_url = f"{settings.frontend_base_url}/register?token={raw_token}"
    defer_after_commit(lambda: _send_invite_email(_email, registration_url))

    return InviteTokenRead.model_validate(record)


async def list_invites(
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
    status: InviteTokenStatus | None = None,
) -> CursorPage[InviteTokenRead]:
    """One page of invite records, newest first; marks expired ones in bulk first.

    When `status` is provided, only rows with that status are returned. The
    dashboard inbox and the invites tab both pass `status=PENDING` to count
    only open invites.
    """
    now = datetime.now(timezone.utc)
    await session.execute(
        update(InviteToken)
        .where(
            InviteToken.status == InviteTokenStatus.PENDING,  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
            InviteToken.expires_at < now,  # type: ignore[operator]  # SQLAlchemy column comparison; stubs incomplete
        )
        .values(status=InviteTokenStatus.EXPIRED)
    )

    page_size = clamp_limit(limit)
    base = select(InviteToken)
    if status is not None:
        base = base.where(InviteToken.status == status)  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
    query = apply_cursor(
        base,
        sort_col=InviteToken.created_at,  # pyright: ignore[reportArgumentType]
        id_col=InviteToken.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
    )
    rows = list((await session.execute(query)).scalars().all())
    return build_cursor_page(
        rows,
        serializer=InviteTokenRead.model_validate,
        cursor_key=lambda r: (r.created_at, r.id),
        limit=page_size,
    )


async def revoke_invite(token_id: int, session: AsyncSession) -> None:
    """Revoke a pending invite: mark as revoked in DB."""
    result = await session.execute(
        select(InviteToken).where(InviteToken.id == token_id)  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise InviteNotFoundError(f"Invite token with ID {token_id} not found")
    if record.status != InviteTokenStatus.PENDING:
        raise InviteAlreadyRevokedError(
            f"Invite {token_id} cannot be revoked (status: {record.status})"
        )

    record.status = InviteTokenStatus.REVOKED
    await session.flush()


async def delete_invite(token_id: int, session: AsyncSession) -> None:
    """Hard-delete an invite row.

    Distinct from `revoke_invite`: revoke preserves the row with status=REVOKED
    so the audit trail survives, while delete removes the record entirely.
    """
    result = await session.execute(
        select(InviteToken).where(InviteToken.id == token_id)  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise InviteNotFoundError(f"Invite token with ID {token_id} not found")
    await session.delete(record)
    await session.flush()


async def resend_invite(token_id: int, session: AsyncSession) -> None:
    """Generate a fresh token for an existing invite and resend the email."""
    result = await session.execute(
        select(InviteToken).where(InviteToken.id == token_id)  # type: ignore[arg-type]  # SQLAlchemy column comparison; stubs incomplete
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise InviteNotFoundError(f"Invite token with ID {token_id} not found")
    if record.status == InviteTokenStatus.USED:
        raise InviteAlreadyRevokedError(
            f"Invite {token_id} has already been used and cannot be resent"
        )

    new_raw, new_hash, new_expires_at = await generate_invite_token()
    record.token_hash = new_hash
    record.expires_at = new_expires_at
    record.status = InviteTokenStatus.PENDING
    await session.flush()

    registration_url = f"{settings.frontend_base_url}/register?token={new_raw}"
    await _send_invite_email(record.email, registration_url)
