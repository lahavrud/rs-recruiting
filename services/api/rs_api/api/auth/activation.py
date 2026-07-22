"""Account activation endpoint (company + candidate)."""

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.infrastructure.dependencies import client_ip
from rs_api.infrastructure.error_handling import service_exception_to_http
from rs_api.infrastructure.limiter import get_limiter
from rs_shared.core.infrastructure.config import settings
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.core.tasks import queue_email
from rs_shared.enums import UserRole
from rs_shared.services.auth.activation import activate_user
from rs_shared.services.exceptions import InvalidActivationTokenError
from rs_shared.templates.email import build_candidate_welcome_html

limiter = get_limiter()
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/activate", status_code=status.HTTP_200_OK)
@limiter.limit("5/hour")
async def activate(
    request: Request,
    token: str = Query(
        ..., description="One-time activation token from the activation email"
    ),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Activate a user account (company or candidate) using the one-time token.

    Dispatches by role inside `activate_user`; for candidates this also
    creates / links their CandidateProfile and records consent.
    """
    try:
        async with transactional(session):
            user = await activate_user(
                token,
                session,
                ip_address=client_ip(request),
                user_agent=request.headers.get("user-agent"),
            )

            # Candidate-only: queue the post-activation explainer email inside
            # the same transaction, so it either lands with the activation or
            # not at all. (It used to be a post-commit hook wrapped in a
            # best-effort try/except, because a hook raising *after* a
            # committed activation returned a 500 for work that had actually
            # succeeded — the client then showed "token invalid" and retried
            # into a 409. Writing the row transactionally removes that split
            # outcome.) Company welcomes go through the approval-email flow.
            if user.role == UserRole.CANDIDATE:
                # The candidate's session isn't authenticated when they
                # open the welcome email; route every CTA through
                # /login?redirect=... so the next click lands on a sign-in
                # screen and forwards to the intended destination after
                # the credential flow.
                jobs_url = f"{settings.frontend_base_url}/login?redirect=/jobs"
                profile_url = (
                    f"{settings.frontend_base_url}/login?redirect=/candidate/profile"
                )
                await queue_email(
                    session,
                    to=user.email,
                    subject="ברוכים הבאים ל-RS Recruiting",
                    body=(
                        "החשבון שלכם הופעל. כעת תוכלו להתחבר ולנהל"
                        " את ההגשות שלכם.\n"
                        f"מועדי משרות פתוחים: {jobs_url}\n"
                        f"פרופיל אישי: {profile_url}\n"
                    ),
                    html_body=build_candidate_welcome_html(
                        jobs_url=jobs_url, profile_url=profile_url
                    ),
                )
    except InvalidActivationTokenError as e:
        raise service_exception_to_http(e) from e

    return {"message": "החשבון הופעל בהצלחה"}
