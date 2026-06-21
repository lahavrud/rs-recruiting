"""Candidate GDPR data export endpoints.

Two endpoints:

* ``POST /api/candidate/me/export`` — authenticated; enqueues the
  Arq build task, returns 202. Per-user rate limit is enforced by
  counting unused-and-unexpired ``DataExportRequest`` rows (one less
  Redis dependency).

* ``GET /api/candidate/me/export/{token}`` — public (the token IS auth);
  streams the assembled ZIP and marks ``used=True``. Authenticated state
  is NOT required because the email link is the proof.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import get_current_candidate
from src.core.infrastructure.limiter import get_limiter
from src.core.infrastructure.security import hash_token
from src.core.infrastructure.transactions import defer_after_commit, transactional
from src.core.services.storage import get_storage_provider
from src.core.tasks import enqueue_data_export_task
from src.models import CandidateProfile, User
from src.services.candidate.data_export import (
    get_export_request_by_token_hash,
    has_pending_export,
)

router = APIRouter(prefix="/api/candidate", tags=["candidate"])
limiter = get_limiter()
logger = logging.getLogger(__name__)


@router.post("/me/export", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/day")
async def request_export(
    request: Request,
    current: tuple[User, CandidateProfile] = Depends(get_current_candidate),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Enqueue the GDPR export build for the calling candidate.

    Existing unused request → 429 (one active export at a time per
    user — the row itself acts as the rate limit, no Redis needed).
    """
    user, _profile = current
    assert user.id is not None

    if await has_pending_export(user.id, session):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="export_already_pending",
        )

    user_id = user.id

    async with transactional(session):
        defer_after_commit(lambda: enqueue_data_export_task(user_id))

    return {"message": "אנו מכינים את הקובץ ונשלח אליכם קישור להורדה."}


@router.get("/me/export/{token}")
async def download_export(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Stream the candidate's prepared ZIP.

    No auth — the unguessable token IS the credential. On success the
    row is marked used so the link is single-use.
    """
    record = await get_export_request_by_token_hash(hash_token(token), session)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="export_not_found"
        )
    if record.used:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="export_already_used"
        )
    now = datetime.now(timezone.utc)
    if record.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="export_expired")

    storage = get_storage_provider()
    try:
        body = await storage.download_file(record.download_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="export_storage_error",
        ) from e

    async with transactional(session):
        record.used = True

    filename = f"rs-recruiting-export-{record.created_at:%Y%m%d}.zip"
    return Response(
        content=body,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
