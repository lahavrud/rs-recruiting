#!/usr/bin/env python3
"""Break-glass: turn MFA off for one user and end all their sessions.

Their next login is password-only and an admin is sent straight to enrolment.
Runbook (incl. how to run this against prod): docs/runbooks/mfa-reset.md.

Usage:
    python scripts/reset_mfa.py --email admin@example.com --reason "lost phone"
"""

import argparse
import asyncio
import sys

from rs_shared.core.infrastructure.database import async_session
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.services.auth.mfa_reset import reset_user_mfa


async def _run(email: str, reason: str) -> bool:
    async with async_session() as session:
        async with transactional(session):
            return await reset_user_mfa(session, email, reason=reason)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--reason", required=True, help="recorded in the audit log")
    args = parser.parse_args()

    if not asyncio.run(_run(args.email, args.reason)):
        print(f"No user with email {args.email!r}; nothing changed.")
        sys.exit(1)
    print(f"MFA reset and all sessions ended for {args.email}.")


if __name__ == "__main__":
    main()
