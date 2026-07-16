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
    uv run python scripts/export_openapi.py    # (re)write frontend/openapi.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# The app instantiates Settings at import time; provide the minimum env the
# spec export needs. These are placeholders — never used to connect to anything
# (openapi() only introspects routes and Pydantic models). Match test bootstrap.
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "openapi-export-placeholder-key-32chars!",  # pragma: allowlist secret
)
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://placeholder:placeholder@localhost/placeholder",  # pragma: allowlist secret  # noqa: E501
)

from rs_api.main import app  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "frontend" / "openapi.json"


def render_spec() -> str:
    """Return the OpenAPI spec as deterministic JSON with a trailing newline."""
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    # newline="\n" so the file is byte-identical on every platform (write_text's
    # default translates \n -> \r\n on Windows, which would diff against the
    # committed LF spec and defeat the drift gate for Windows contributors).
    SPEC_PATH.write_text(render_spec(), newline="\n")
    print(f"Wrote {SPEC_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
