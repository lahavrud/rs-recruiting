"""Candidate GDPR account deletion endpoints.

Three endpoints:

* ``POST /api/candidate/me/deletion-request`` — authenticated; uses the
  current candidate's email to initiate deletion. 202 regardless of outcome
  (email-enumeration protection).

* ``POST /api/candidate/deletion-request`` — public; accepts an ``email``
  body field. For anonymous candidates who applied without registering.
  202 regardless of outcome.

* ``GET /api/candidate/deletion-confirm`` — public; ``?token=<raw>`` query
  param. Validates without consuming — lets the frontend gate the confirm
  page on a usable link.

* ``POST /api/candidate/deletion-confirm`` — public; ``{"token": "..."}``
  body. Executes the deletion atomically and returns 204.
"""

import logging

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.infrastructure.dependencies import get_current_candidate
from rs_api.infrastructure.error_handling import service_exception_to_http
from rs_api.infrastructure.limiter import get_limiter
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.core.services.storage import get_storage_provider
from rs_shared.models import CandidateProfile, User
from rs_shared.services.candidate.account_deletion import (
    check_deletion_token,
    confirm_deletion,
    request_account_deletion,
)
from rs_shared.services.exceptions import InvalidAccountDeletionTokenError

router = APIRouter(prefix="/api/candidate", tags=["candidate"])
limiter = get_limiter()
logger = logging.getLogger(__name__)


class _DeletionRequestBody(BaseModel):
    email: EmailStr


class _DeletionConfirmBody(BaseModel):
    token: str


@router.post("/me/deletion-request", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/day")
async def request_deletion_authenticated(
    request: Request,
    current: tuple[User, CandidateProfile] = Depends(get_current_candidate),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Initiate account deletion for the authenticated candidate.

    Sends a confirmation email with a 24-hour link. Always 202.
    """
    user, _profile = current
    ip = request.client.host if request.client else None

    async with transactional(session):
        await request_account_deletion(
            user.email,
            session,
            ip_address=ip,
        )
    return {"message": "אם הכתובת קיימת במערכת, נשלח אליה קישור לאישור המחיקה."}


@router.post("/deletion-request", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/day")
async def request_deletion_anonymous(
    body: _DeletionRequestBody,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Initiate account deletion by email (anonymous path).

    For candidates who applied via the public form without registering.
    Always 202 regardless of whether the email matches a profile.
    """
    ip = request.client.host if request.client else None

    async with transactional(session):
        await request_account_deletion(
            str(body.email),
            session,
            ip_address=ip,
        )
    return {"message": "אם הכתובת קיימת במערכת, נשלח אליה קישור לאישור המחיקה."}


@router.get("/deletion-confirm")
async def validate_deletion_token(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Validate an account deletion token without consuming it.

    200 if the token is valid; 400 if invalid / expired / already used.
    """
    try:
        await check_deletion_token(token, session)
    except InvalidAccountDeletionTokenError as exc:
        raise service_exception_to_http(exc) from exc
    return {"valid": True}


@router.post("/deletion-confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_deletion_endpoint(
    body: _DeletionConfirmBody,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Execute the account deletion identified by the token.

    Atomically tombstones the candidate profile, scrubs application resume
    snapshots, and deletes the linked user account.  204 on success; 400 if
    the token is invalid / expired / already used.
    """
    storage = get_storage_provider()
    try:
        async with transactional(session):
            await confirm_deletion(body.token, session, storage=storage)
    except InvalidAccountDeletionTokenError as exc:
        raise service_exception_to_http(exc) from exc
