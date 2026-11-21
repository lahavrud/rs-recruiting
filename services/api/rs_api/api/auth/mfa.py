"""TOTP second factor endpoints: enrolment, the login code step, recovery codes.

Policy lives in ``rs_shared.services.auth.mfa`` / ``mfa_challenge``. Enrolment
is admin-only for now (#1177); the login code step applies to any user with MFA
on. Every response here carries a secret, codes or tokens: ``no-store``.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.api.auth.login import issue_session
from rs_api.infrastructure.dependencies import (
    client_ip,
    get_current_admin,
    get_current_admin_pre_mfa,
    get_token_payload,
)
from rs_api.infrastructure.error_handling import service_exception_to_http
from rs_api.infrastructure.limiter import get_limiter
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.models import User
from rs_shared.schemas.auth import (
    LoginResponse,
    MfaCodeRequest,
    MfaEnrolmentConfirmResponse,
    MfaEnrolmentStartResponse,
    MfaRecoveryCodesResponse,
    MfaStatusResponse,
    MfaVerifyRequest,
)
from rs_shared.services.auth.mfa import (
    confirm_enrolment,
    mfa_status,
    regenerate_recovery_codes,
    start_enrolment,
)
from rs_shared.services.auth.mfa_challenge import verify_challenge
from rs_shared.services.auth.session import build_access_token
from rs_shared.services.exceptions import (
    AccountLockedError,
    InvalidMfaCodeError,
    MfaAlreadyEnabledError,
    MfaChallengeExpiredError,
    MfaLockedError,
    MfaNotEnrolledError,
)

logger = logging.getLogger(__name__)
limiter = get_limiter()


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/auth/mfa", tags=["auth"], dependencies=[Depends(_no_store)])


@router.post("/enrol/start", response_model=MfaEnrolmentStartResponse)
@limiter.limit("10/hour")
async def enrol_start(
    request: Request,
    user: User = Depends(get_current_admin_pre_mfa),
    session: AsyncSession = Depends(get_session),
) -> MfaEnrolmentStartResponse:
    """Issue a pending TOTP secret (QR rendered client-side from the URI)."""
    try:
        async with transactional(session):
            secret, uri = await start_enrolment(session, user)
    except MfaAlreadyEnabledError as e:
        raise service_exception_to_http(e) from e
    return MfaEnrolmentStartResponse(secret=secret, otpauth_uri=uri)


@router.post("/enrol/confirm", response_model=MfaEnrolmentConfirmResponse)
@limiter.limit("10/hour")
async def enrol_confirm(
    request: Request,
    body: MfaCodeRequest,
    user: User = Depends(get_current_admin_pre_mfa),
    payload: dict[str, Any] = Depends(get_token_payload),
    session: AsyncSession = Depends(get_session),
) -> MfaEnrolmentConfirmResponse:
    """Confirm enrolment with a code: MFA on, recovery codes, other sessions out.

    Returns a fresh access token for the same session, no re-login needed.
    """
    sid = payload.get("sid")
    try:
        async with transactional(session):
            codes = await confirm_enrolment(
                session,
                user,
                body.code,
                keep_session_id=sid,
                client_ip=client_ip(request),
            )
    except (MfaAlreadyEnabledError, MfaNotEnrolledError, InvalidMfaCodeError) as e:
        raise service_exception_to_http(e) from e

    # Same session (sid), now MFA-verified: the SPA's ``mfa`` claim flips.
    access_token = build_access_token(user, sid=sid, mfa=True)
    return MfaEnrolmentConfirmResponse(recovery_codes=codes, access_token=access_token)


@router.post("/verify", response_model=LoginResponse)
@limiter.limit("10/minute")
async def verify(
    request: Request,
    response: Response,
    body: MfaVerifyRequest,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    """Finish a login: challenge + TOTP (or a recovery code) → tokens."""
    try:
        async with transactional(session):
            user, remember_me = await verify_challenge(
                session,
                body.mfa_token,
                code=body.code,
                recovery_code=body.recovery_code,
                client_ip=client_ip(request),
            )
    except (
        MfaChallengeExpiredError,
        InvalidMfaCodeError,
        MfaLockedError,
        AccountLockedError,
    ) as e:
        raise service_exception_to_http(e) from e

    access_token = await issue_session(
        request, response, session, user, remember_me=remember_me, mfa_verified=True
    )
    return LoginResponse(access_token=access_token)


@router.post("/recovery-codes", response_model=MfaRecoveryCodesResponse)
@limiter.limit("5/hour")
async def new_recovery_codes(
    request: Request,
    body: MfaCodeRequest,
    user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> MfaRecoveryCodesResponse:
    """Replace the recovery codes (requires a current code)."""
    try:
        async with transactional(session):
            codes = await regenerate_recovery_codes(
                session, user, body.code, client_ip=client_ip(request)
            )
    except (MfaNotEnrolledError, InvalidMfaCodeError) as e:
        raise service_exception_to_http(e) from e
    return MfaRecoveryCodesResponse(recovery_codes=codes)


@router.get("/status", response_model=MfaStatusResponse)
@limiter.limit("60/minute")
async def get_status(
    request: Request,
    user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> MfaStatusResponse:
    """MFA on/off and how many recovery codes are left."""
    assert user.id is not None
    enabled, remaining = await mfa_status(session, user.id)
    return MfaStatusResponse(enabled=enabled, recovery_codes_remaining=remaining)
