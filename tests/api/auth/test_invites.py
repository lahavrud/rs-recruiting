"""Tests for public invite token endpoints.

Validation runs for real against invite rows (``real_invite_tokens``), not
through the suite-wide ``mock_invite_tokens`` stub.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from rs_shared.enums import InviteTokenStatus
from rs_shared.models import InviteToken

pytestmark = [pytest.mark.asyncio, pytest.mark.real_invite_tokens]

MakeInvite = Callable[..., Awaitable[InviteToken]]


async def test_get_invite_metadata_returns_fields(
    public_client: AsyncClient, make_invite: MakeInvite
):
    """Valid token returns email and company pre-fill data."""
    await make_invite(
        "valid-token-abc",
        company_name="Test Co",
        contact_first_name="ישראל",
        contact_last_name="ישראלי",
    )

    response = await public_client.get("/auth/invite/valid-token-abc")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "company@example.com"
    # InviteMetadataPublic only exposes email — no pre-fill fields


async def test_get_invite_metadata_null_optional_fields(
    public_client: AsyncClient, make_invite: MakeInvite
):
    """Invite with no company/contact info still returns email only."""
    await make_invite("sparse-token")

    response = await public_client.get("/auth/invite/sparse-token")

    assert response.status_code == 200
    data = response.json()
    assert "email" in data


async def test_get_invite_metadata_token_not_in_db_returns_400(
    public_client: AsyncClient,
):
    response = await public_client.get("/auth/invite/no-db-record")

    assert response.status_code == 400


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"status": InviteTokenStatus.USED}, id="used"),
        pytest.param({"status": InviteTokenStatus.REVOKED}, id="revoked"),
        pytest.param(
            {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)},
            id="expired",
        ),
    ],
)
async def test_get_invite_metadata_unusable_token_returns_400(
    public_client: AsyncClient, make_invite: MakeInvite, fields: dict
):
    """A row that exists but can no longer be used must not pre-fill the form."""
    await make_invite("unusable-token", **fields)

    response = await public_client.get("/auth/invite/unusable-token")

    assert response.status_code == 400
