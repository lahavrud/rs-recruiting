#!/usr/bin/env python3
"""Backfill: enqueue embedding tasks for jobs and candidates.

Originally written for the embed-v4.0 migration (c9e3edf3bd29), which nulled
every vector and needed a full re-embed. `--missing-only` narrows it to rows
that have no vector at all, which is the safer routine repair: re-embedding a
candidate also re-runs CV extraction and LLM summarisation, so a blanket run
is expensive.

Usage (via a one-off ECS task derived from the live web task-def):
    uv run scripts/backfill_embeddings.py --dry-run
    uv run scripts/backfill_embeddings.py --jobs-only --missing-only

Requires:
    SQS_QUEUE_URL       set (otherwise tasks run inline — local dev only)
    EMBEDDING_PROVIDER  cohere
    EMBEDDING_API_KEY   <cohere key from SSM>
"""

import argparse
import asyncio

from sqlalchemy import select

from rs_shared.core.infrastructure.database import async_session
from rs_shared.core.tasks import enqueue_embed_job_task, enqueue_match_candidate_task
from rs_shared.enums import JobStatus
from rs_shared.models import CandidateProfile, Job


async def _collect_ids(
    *, missing_only: bool, jobs_only: bool
) -> tuple[list[int], list[int]]:
    """Return (job_ids, candidate_ids) to backfill."""
    async with async_session() as session:
        # Only PUBLISHED jobs are matchable, so they're the only ones whose
        # missing vector is user-visible (empty applications / AI columns).
        job_stmt = select(Job.id)
        if missing_only:
            job_stmt = job_stmt.where(
                Job.status == JobStatus.PUBLISHED,
                Job.embedding.is_(None),
            )
        job_ids = list((await session.execute(job_stmt)).scalars().all())

        if jobs_only:
            return job_ids, []

        cand_stmt = select(CandidateProfile.id).where(
            CandidateProfile.resume_path.is_not(None)
        )
        if missing_only:
            cand_stmt = cand_stmt.where(CandidateProfile.embedding.is_(None))
        candidate_ids = list((await session.execute(cand_stmt)).scalars().all())
    return job_ids, candidate_ids


async def run(*, dry_run: bool, missing_only: bool, jobs_only: bool) -> None:
    job_ids, candidate_ids = await _collect_ids(
        missing_only=missing_only, jobs_only=jobs_only
    )

    scope = "missing vectors only" if missing_only else "ALL rows (full re-embed)"
    print(f"Scope: {scope}{' — jobs only' if jobs_only else ''}")
    print(f"Jobs to embed:       {len(job_ids)} {job_ids}")
    print(f"Candidates to embed: {len(candidate_ids)}")

    if dry_run:
        print("\n--dry-run: no tasks enqueued.")
        return

    for job_id in job_ids:
        await enqueue_embed_job_task(job_id)
        print(f"  enqueued embed_job       job_id={job_id}")

    for candidate_id in candidate_ids:
        await enqueue_match_candidate_task(candidate_id)
        print(f"  enqueued match_candidate candidate_id={candidate_id}")

    print(
        f"\nDone. Enqueued {len(job_ids)} job + {len(candidate_ids)} candidate tasks."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts without enqueuing any tasks.",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Only rows with no vector (PUBLISHED jobs / candidates with a resume).",
    )
    parser.add_argument(
        "--jobs-only",
        action="store_true",
        help="Skip candidates — candidate re-embedding also re-runs CV extraction.",
    )
    args = parser.parse_args()
    asyncio.run(
        run(
            dry_run=args.dry_run,
            missing_only=args.missing_only,
            jobs_only=args.jobs_only,
        )
    )


if __name__ == "__main__":
    main()
