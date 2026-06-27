"""Tests for admin match-feed endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_matches_empty(admin_client: AsyncClient):
    """Matches endpoint returns an empty list when no embeddings exist."""
    response = await admin_client.get("/api/admin/matches")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_hot_matches_empty(admin_client: AsyncClient):
    """Hot matches endpoint returns an empty list when no applications exist."""
    response = await admin_client.get("/api/admin/matches/hot")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_matches_requires_auth(client: AsyncClient):
    """Match endpoints reject unauthenticated requests."""
    response = await client.get("/api/admin/matches")
    assert response.status_code == 401
