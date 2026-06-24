"""Resume-matching task implementations (consumer side).

Split out of ``tasks.py`` to keep that module focused on the SQS
producer/registry plumbing. The ``enqueue_*`` wrappers and ``TASK_REGISTRY``
live in ``tasks.py`` and reference the functions defined here.

Both tasks are plain async functions (no Arq ctx arg), dispatched by the SQS
worker and run inline in local dev. Both are idempotent so SQS at-least-once
redelivery is safe.
"""

import logging

from src.core.infrastructure.database import async_session
from src.core.infrastructure.transactions import transactional

logger = logging.getLogger(__name__)


def _extension_of(name: str | None) -> str:
    """Bare lowercase extension (no dot) for a filename/key; '' when none."""
    if not name or "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


def cosine_similarity_score(distance: float) -> float:
    """Map a pgvector cosine distance (∈ [0, 2]) to a similarity in [0, 1]."""
    return max(0.0, min(1.0, 1.0 - float(distance)))


async def embed_job_task(job_id: int) -> None:
    """Compute and store a job's embedding. Triggered on publish/edit.

    No-op if the job is gone or renders to empty text. Idempotent — safe under
    SQS at-least-once redelivery (recomputes the same vector).
    """
    from src.core.services.cv_extraction import job_embedding_text
    from src.core.services.embeddings import get_embedding_provider
    from src.models import Job

    async with async_session() as session:
        async with transactional(session):
            job = await session.get(Job, job_id)
            if job is None:
                logger.info("embed_job_skipped_missing", extra={"job_id": job_id})
                return
            text = job_embedding_text(job)
            if not text:
                return
            [vector] = await get_embedding_provider().embed(
                [text], input_type="search_document"
            )
            job.embedding = vector
    logger.info("job_embedded", extra={"job_id": job_id})


async def match_candidate_task(candidate_id: int) -> None:
    """Extract and embed a candidate's CV so they can be matched against jobs.

    Steps: download resume → extract text → store ``parsed_text`` → embed →
    store ``embedding``. Idempotent — safe under SQS at-least-once redelivery
    (recomputes the same text/vector). The actual job matching is a live
    cosine-distance query at read time (see ``services.admin.candidates`` and
    ``services.admin.jobs``), not persisted here.

    Skips cleanly (leaving prior ``parsed_text``/``embedding`` untouched) when
    there is no resume or the file yields no extractable text (e.g. legacy
    ``.doc``).
    """
    from src.core.services.cv_extraction import extract_text
    from src.core.services.embeddings import get_embedding_provider
    from src.core.services.storage import get_storage_provider
    from src.models import CandidateProfile

    async with async_session() as session:
        async with transactional(session):
            profile = await session.get(CandidateProfile, candidate_id)
            if profile is None or not profile.resume_path:
                logger.info(
                    "match_skipped_no_resume", extra={"candidate_id": candidate_id}
                )
                return

            content = await get_storage_provider().download_file(profile.resume_path)
            ext = _extension_of(profile.resume_filename or profile.resume_path)
            text = extract_text(content, ext)
            if not text:
                logger.info(
                    "match_skipped_no_text", extra={"candidate_id": candidate_id}
                )
                return

            profile.parsed_text = text
            [vector] = await get_embedding_provider().embed(
                [text], input_type="search_query"
            )
            profile.embedding = vector
    logger.info("candidate_embedded", extra={"candidate_id": candidate_id})
