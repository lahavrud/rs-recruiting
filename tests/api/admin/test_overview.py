"""Tests for the admin overview endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_admin_overview_empty(admin_client: AsyncClient):
    """Overview endpoint returns the expected shape with zero counts."""
    response = await admin_client.get("/api/admin/overview")
    assert response.status_code == 200

    data = response.json()
    assert "inbox" in data
    assert "stats" in data
    assert "pulse" in data
    assert data["inbox"]["pending_companies"] == 0
    assert data["inbox"]["pending_jobs"] == 0
    assert data["inbox"]["new_applications"] == 0
    assert data["stats"]["total_candidates"] == 0


@pytest.mark.asyncio
async def test_get_admin_overview_requires_auth(client: AsyncClient):
    """Overview endpoint rejects unauthenticated requests."""
    response = await client.get("/api/admin/overview")
    assert response.status_code == 401
