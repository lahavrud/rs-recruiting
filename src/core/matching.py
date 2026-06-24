"""Resume-matching task implementations (consumer side).

Split out of ``tasks.py`` to keep that module focused on the SQS
producer/registry plumbing. The ``enqueue_*`` wrappers and ``TASK_REGISTRY``
live in ``tasks.py`` and reference the functions defined here.

Both tasks are plain async functions (no Arq ctx arg), dispatched by the SQS
worker and run inline in local dev. Both are idempotent so SQS at-least-once
redelivery is safe.
"""

import logging

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import async_session
from src.core.infrastructure.transactions import transactional

logger = logging.getLogger(__name__)


def _extension_of(name: str | None) -> str:
    """Bare lowercase extension (no dot) for a filename/key; '' when none."""
    if not name or "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


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
    """Embed a candidate's CV and persist their top-N matching jobs.

    Steps: download resume → extract text → store ``parsed_text`` → embed →
    cosine-search PUBLISHED, embedded jobs → replace this candidate's
    ``JobMatch`` rows. Idempotent (delete-then-insert) so SQS redelivery is safe.

    Skips cleanly (leaving any prior matches untouched) when there is no resume
    or the file yields no extractable text (e.g. legacy ``.doc``).
    """
    from sqlalchemy import delete, select

    from src.core.services.cv_extraction import extract_text
    from src.core.services.embeddings import get_embedding_provider
    from src.core.services.storage import get_storage_provider
    from src.enums import JobStatus
    from src.models import CandidateProfile, Job, JobMatch

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
            await session.flush()

            distance = Job.embedding.cosine_distance(vector)
            rows = (
                await session.execute(
                    select(Job.id, distance.label("distance"))
                    .where(
                        Job.status == JobStatus.PUBLISHED,
                        Job.embedding.is_not(None),
                    )
                    .order_by(distance)
                    .limit(settings.embedding_top_matches)
                )
            ).all()

            # Replace this candidate's matches wholesale (idempotent re-run).
            await session.execute(
                delete(JobMatch).where(JobMatch.candidate_id == candidate_id)
            )
            for job_id, dist in rows:
                # cosine_distance ∈ [0, 2]; similarity = 1 - distance, clamped.
                score = max(0.0, min(1.0, 1.0 - float(dist)))
                session.add(
                    JobMatch(candidate_id=candidate_id, job_id=job_id, score=score)
                )
    logger.info(
        "candidate_matched",
        extra={"candidate_id": candidate_id, "match_count": len(rows)},
    )
