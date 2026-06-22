"""Candidate profile primitives: lookup + partial update.

The heavy apply-flow (file validation, storage upload, dup detection,
email side effects) lives in `src/services/applications.py`. This
module only owns the small pieces that operate on a single
`CandidateProfile` row.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CandidateProfile
from src.schemas import CandidateProfileCreate


async def find_candidate_by_email(
    email: str,
    session: AsyncSession,
) -> CandidateProfile | None:
    """The apply flow's dedup key: a guest applying without an account is
    matched to their existing `CandidateProfile` by email rather than by
    `user_id`, since an unauthenticated submitter has no user row to match
    against yet.
    """
    result = await session.execute(
        select(CandidateProfile).where(  # pyright: ignore[reportArgumentType]
            CandidateProfile.email == email
        )
    )
    return result.scalar_one_or_none()


async def update_candidate_profile(
    candidate: CandidateProfile,
    candidate_data: CandidateProfileCreate,
    resume_path: str | None = None,
    resume_filename: str | None = None,
    resume_hash: str | None = None,
    session: AsyncSession | None = None,
) -> CandidateProfile:
    """Update an existing candidate profile with new information.

    Update strategy:
    - Always update: full_name (may have changed), phone (kept in sync with
      whatever the candidate submitted on the apply form so the next
      autofill is accurate).
    - Update if None on profile: linkedin_url, resume_path (don't blow away
      a richer profile value with a sparser apply-form submission).
      resume_filename and resume_hash are always updated as a unit with
      resume_path so they stay in sync.
    - Never overwrite: email, created_at.
    """
    if session is None:
        raise ValueError("Database session is required")

    candidate.full_name = candidate_data.full_name
    candidate.phone = candidate_data.phone

    if candidate.linkedin_url is None and candidate_data.linkedin_url is not None:
        candidate.linkedin_url = candidate_data.linkedin_url
    if candidate.resume_path is None and resume_path is not None:
        candidate.resume_path = resume_path
        candidate.resume_filename = resume_filename
        candidate.resume_hash = resume_hash

    return candidate
