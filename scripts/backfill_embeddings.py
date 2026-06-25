#!/usr/bin/env python3
"""One-time backfill: enqueue embedding tasks for all jobs and candidates.

Run this after deploying the embed-v4.0 migration (c9e3edf3bd29) to prod.
The migration nulls all existing vectors; this script re-enqueues everything
so the SQS worker recomputes embeddings with the new model and dimension.

Usage (via SSM Run Command on the EC2 instance):
    uv run scripts/backfill_embeddings.py
    uv run scripts/backfill_embeddings.py --dry-run

Requires:
    SQS_QUEUE_URL       set (otherwise tasks run inline — local dev only)
    EMBEDDING_PROVIDER  cohere
    EMBEDDING_API_KEY   <cohere key from SSM>
"""

import argparse
import asyncio

from sqlalchemy import select

from src.core.infrastructure.database import async_session
from src.core.tasks import enqueue_embed_job_task, enqueue_match_candidate_task
from src.models import CandidateProfile, Job


async def _collect_ids() -> tuple[list[int], list[int]]:
    """Return (job_ids, candidate_ids) to backfill."""
    async with async_session() as session:
        job_ids = list((await session.execute(select(Job.id))).scalars().all())
        candidate_ids = list(
            (
                await session.execute(
                    select(CandidateProfile.id).where(
                        CandidateProfile.resume_path.is_not(None)
                    )
                )
            )
            .scalars()
            .all()
        )
    return job_ids, candidate_ids


async def run(*, dry_run: bool) -> None:
    job_ids, candidate_ids = await _collect_ids()

    print(f"Jobs to embed:       {len(job_ids)}")
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
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
