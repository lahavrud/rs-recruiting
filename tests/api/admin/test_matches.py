"""Tests for admin match-feed endpoints."""

import pytest
from httpx import AsyncClient

from rs_shared.models import CandidateProfile, Job, User
from tests.conftest import audit_rows


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


@pytest.mark.asyncio
async def test_dismiss_match_is_audited_with_admin_and_ip(
    admin_client: AsyncClient,
    admin_user: User,
    candidate_profile: CandidateProfile,
    published_job: Job,
):
    response = await admin_client.post(
        "/api/admin/matches/dismiss",
        json={
            "candidate_id": candidate_profile.id,
            "job_id": published_job.id,
            "score": 0.7,
        },
    )

    assert response.status_code == 204
    [row] = await audit_rows("match.dismiss")
    assert (row.target_id, row.actor_user_id, row.ip_address) == (
        candidate_profile.id,
        admin_user.id,
        "127.0.0.1",
    )
