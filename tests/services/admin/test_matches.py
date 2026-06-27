"""Unit tests for the admin match-feed service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.admin.matches import get_global_matches, get_hot_applications


@pytest.mark.asyncio
async def test_get_global_matches_empty_db(session: AsyncSession):
    """Returns an empty list when no candidates have embeddings."""
    result = await get_global_matches(session)
    assert result == []


@pytest.mark.asyncio
async def test_get_hot_applications_empty_db(session: AsyncSession):
    """Returns an empty list when no applications exist."""
    result = await get_hot_applications(session)
    assert result == []
