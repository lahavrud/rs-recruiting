"""Candidate self-registration + resend-activation endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import client_ip
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.limiter import get_limiter
from src.core.infrastructure.transactions import transactional
from src.schemas import CandidateRegisterRequest, ResendActivationRequest
from src.services.auth.candidate_registration import (
    register_candidate,
    resend_candidate_activation,
)
from src.services.exceptions import EmailAlreadyExistsError

limiter = get_limiter()
router = APIRouter(prefix="/auth/candidate", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("3/hour")
async def register(
    request: Request,
    body: CandidateRegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Register a new candidate user.

    Returns 201 with a generic "check your email" hint on success. Raises
    409 ``email_already_exists`` when the email belongs to an active user
    or to a pending non-candidate slot — UX choice: the user is told the
    account exists so they can switch to the login form, instead of
    silently re-running the request. Per-IP slowapi 3/hour limits brute
    enumeration via this signal.
    """
    if not body.privacy_accepted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="יש לאשר את מדיניות הפרטיות",
        )
    if not body.terms_accepted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="יש לאשר את תנאי השימוש",
        )

    try:
        async with transactional(session):
            await register_candidate(
                body.email,
                body.password,
                body.full_name,
                privacy_accepted=body.privacy_accepted,
                terms_accepted=body.terms_accepted,
                session=session,
                ip_address=client_ip(request),
                user_agent=request.headers.get("user-agent"),
            )
    except EmailAlreadyExistsError as e:
        raise service_exception_to_http(e) from e

    return {"message": "אנא בדקו את תיבת הדואר שלכם להפעלת החשבון"}


@router.post(
    "/resend-activation",
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("5/hour")
async def resend_activation(
    request: Request,
    body: ResendActivationRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Resend the candidate activation email (silent 202 in all cases)."""
    async with transactional(session):
        await resend_candidate_activation(
            body.email,
            session=session,
            ip_address=client_ip(request),
        )
    return {"message": "אם החשבון קיים וטרם הופעל, שלחנו לכם קישור חדש"}
