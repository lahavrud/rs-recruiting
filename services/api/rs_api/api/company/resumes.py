"""Resume download endpoint — streams bytes from local storage or S3."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from rs_api.api._resume_streaming import stream_resume
from rs_api.infrastructure.dependencies import client_ip, get_current_admin
from rs_shared.core.infrastructure.database import get_session
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.models import User
from rs_shared.services.admin.resume_access import audit_resume_view

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


@router.get("/{file_key}")
async def download_resume(
    request: Request,
    file_key: str,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Secure proxy: streams resume bytes from local storage or S3.

    Each successful view is audited against the candidate; a rejected key or a
    missing file raises first, so it is never recorded as a view.
    """
    response = await stream_resume(file_key)
    async with transactional(session):
        await audit_resume_view(
            session,
            file_key,
            actor_user_id=current_admin.id,
            ip_address=client_ip(request),
        )
    return response
