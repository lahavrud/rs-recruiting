"""Company registration endpoint."""

import json

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import client_ip
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.invite_tokens import validate_invite_token
from src.core.infrastructure.limiter import get_limiter
from src.core.infrastructure.transactions import transactional
from src.core.services.file_validation import validate_upload
from src.schemas import CompanyProfileCreate, UserCreate, UserWithCompanyRead
from src.services.auth.registration import (
    CompanyRegistrationData,
    register_company_user,
)
from src.services.auth.session import mark_invite_used
from src.services.exceptions import EmailAlreadyExistsError, InvalidInviteTokenError

limiter = get_limiter()
router = APIRouter(prefix="/auth", tags=["auth"])

_LOGO_ALLOWED_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
_LOGO_MAX_BYTES = 2 * 1024 * 1024


@router.post(
    "/register",
    response_model=UserWithCompanyRead,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("3/hour")
async def register(
    request: Request,
    token: str = Query(..., description="Single-use invite token issued by an admin"),
    email: str = Form(...),
    password: str = Form(...),
    company_name: str = Form(...),
    company_id: str = Form(...),
    address: str = Form(...),
    contact_first_name: str = Form(...),
    contact_last_name: str = Form(...),
    contact_mobile_phone: str = Form(...),
    contact_landline_phone: str | None = Form(None),
    agreement_signature: str = Form(...),
    privacy_accepted: bool = Form(...),
    terms_accepted: bool = Form(...),
    logo: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> UserWithCompanyRead:
    """Register a new company user with a valid single-use invite token."""
    if not privacy_accepted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="יש לאשר את מדיניות הפרטיות",
        )
    if not terms_accepted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="יש לאשר את תנאי השימוש",
        )
    try:
        profile_data = CompanyProfileCreate(
            name=company_name,
            company_id=company_id,
            address=address,
            contact_first_name=contact_first_name,
            contact_last_name=contact_last_name,
            contact_mobile_phone=contact_mobile_phone,
            contact_landline_phone=contact_landline_phone,
        )
        user_create = UserCreate(
            email=email.lower().strip(), password=password, company_profile=profile_data
        )
    except PydanticValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=json.loads(exc.json()),
        ) from exc

    logo_content = await validate_upload(logo, _LOGO_ALLOWED_TYPES, _LOGO_MAX_BYTES)
    logo_filename = logo.filename or "logo"
    logo_content_type = logo.content_type

    try:
        async with transactional(session):
            await validate_invite_token(token, session)
            result = await register_company_user(
                user_create,
                session,
                logo_content,
                logo_filename,
                CompanyRegistrationData(
                    logo_content_type=logo_content_type,
                    agreement_signature=agreement_signature,
                    privacy_accepted=privacy_accepted,
                    terms_accepted=terms_accepted,
                    acceptance_ip=client_ip(request),
                    acceptance_user_agent=request.headers.get("user-agent"),
                ),
            )
            await mark_invite_used(token, session)
    except InvalidInviteTokenError as e:
        raise service_exception_to_http(e) from e
    except EmailAlreadyExistsError as e:
        raise service_exception_to_http(e) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="registration_failed",
        ) from e
    except sqlalchemy_exc.IntegrityError as e:
        pgcode = getattr(e.orig, "pgcode", None)
        if pgcode == "23505":  # unique_violation
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="email_already_exists",
            ) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="registration_failed",
        ) from e

    return result
