#!/usr/bin/env python3
"""Export the FastAPI OpenAPI spec to a stable, committed JSON artifact.

This is the single source of truth for the frontend/backend contract. The
committed spec (`frontend/openapi.json`) is regenerated in CI and diffed:

- `backend-checks` runs this script and `git diff --exit-code`s the output, so a
  backend schema change that isn't reflected in the committed spec fails the build.
- `frontend-checks` regenerates `src/types/generated.ts` from the committed spec
  and diffs that, so the TypeScript types can't drift from the spec.

Output is deterministic (``sort_keys=True``, trailing newline) so the diff is
stable across machines and Python runs.

Usage:
    uv run python scripts/export_openapi.py            # write frontend/openapi.json
    uv run python scripts/export_openapi.py --check     # exit 1 if the file is stale
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# The app instantiates Settings at import time; provide the minimum env the
# spec export needs. These are never used to connect to anything — openapi()
# only introspects routes and Pydantic models. Match test bootstrap values.
os.environ.setdefault("JWT_SECRET_KEY", "openapi-export-placeholder-key-32chars!")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://placeholder:placeholder@localhost/placeholder"
)

from rs_api.main import app  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "frontend" / "openapi.json"


def render_spec() -> str:
    """Return the OpenAPI spec as deterministic JSON with a trailing newline."""
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the committed spec is stale (does not write).",
    )
    args = parser.parse_args()

    rendered = render_spec()

    if args.check:
        current = SPEC_PATH.read_text() if SPEC_PATH.exists() else ""
        if current != rendered:
            print(
                f"{SPEC_PATH.relative_to(REPO_ROOT)} is stale — run "
                "`uv run python scripts/export_openapi.py` and commit the result.",
                file=sys.stderr,
            )
            return 1
        return 0

    SPEC_PATH.write_text(rendered)
    print(f"Wrote {SPEC_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
