"""Model tests for LoginThrottle."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from rs_shared.models import LoginThrottle


def _row(ip: str = "203.0.113.1") -> LoginThrottle:
    return LoginThrottle(
        email_hash="a" * 64,
        client_ip=ip,
        failures=1,
        last_failure_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_one_row_per_email_and_ip(session):
    """The (email_hash, client_ip) unique constraint is the upsert target."""
    session.add(_row())
    session.add(_row(ip="203.0.113.2"))
    await session.flush()

    session.add(_row())
    with pytest.raises(IntegrityError):
        await session.flush()


def test_table_shape_matches_migration():
    """Kept in step with alembic f8a12f04ae35 (create_all builds dev/test)."""
    table = LoginThrottle.__table__  # type: ignore[attr-defined]
    assert table.name == "login_throttle"
    assert {c.name for c in table.columns} == {
        "id",
        "email_hash",
        "client_ip",
        "failures",
        "last_failure_at",
        "blocked_until",
    }
    assert {i.name for i in table.indexes} == {"ix_login_throttle_last_failure_at"}
