"""Candidate endpoints for public application form."""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.api.public._apply_handler import apply_to_job
from rs_api.infrastructure.dependencies import get_current_user_optional
from rs_shared.core.infrastructure.database import get_session
from rs_shared.models import User
from rs_shared.schemas import ApplicationSubmitted

router = APIRouter(prefix="/api/candidates", tags=["candidates"])
jobs_apply_router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post(
    "/apply",
    response_model=ApplicationSubmitted,
    status_code=status.HTTP_201_CREATED,
)
async def apply_to_job_endpoint(
    request: Request,
    job_id: int = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    linkedin_url: str | None = Form(None),
    service_concept: str | None = Form(None, max_length=2000),
    salary_expectations: str | None = Form(None, max_length=2000),
    growth_area: str | None = Form(None, max_length=2000),
    strength: str | None = Form(None, max_length=2000),
    privacy_accepted: bool = Form(...),
    terms_accepted: bool = Form(...),
    resume: UploadFile | None = File(None),
    password: str | None = Form(None),
    password_confirm: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user_optional),
) -> ApplicationSubmitted:
    return await apply_to_job(
        job_id=job_id,
        full_name=full_name,
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
        service_concept=service_concept,
        salary_expectations=salary_expectations,
        growth_area=growth_area,
        strength=strength,
        privacy_accepted=privacy_accepted,
        terms_accepted=terms_accepted,
        resume=resume,
        password=password,
        password_confirm=password_confirm,
        request=request,
        session=session,
        current_user=current_user,
    )


@jobs_apply_router.post(
    "/{job_id}/apply",
    response_model=ApplicationSubmitted,
    status_code=status.HTTP_201_CREATED,
)
async def apply_to_job_by_path(
    job_id: int,
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    linkedin_url: str | None = Form(None),
    service_concept: str | None = Form(None, max_length=2000),
    salary_expectations: str | None = Form(None, max_length=2000),
    growth_area: str | None = Form(None, max_length=2000),
    strength: str | None = Form(None, max_length=2000),
    privacy_accepted: bool = Form(...),
    terms_accepted: bool = Form(...),
    resume: UploadFile | None = File(None),
    password: str | None = Form(None),
    password_confirm: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user_optional),
) -> ApplicationSubmitted:
    return await apply_to_job(
        job_id=job_id,
        full_name=full_name,
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
        service_concept=service_concept,
        salary_expectations=salary_expectations,
        growth_area=growth_area,
        strength=strength,
        privacy_accepted=privacy_accepted,
        terms_accepted=terms_accepted,
        resume=resume,
        password=password,
        password_confirm=password_confirm,
        request=request,
        session=session,
        current_user=current_user,
    )
