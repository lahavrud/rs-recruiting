#!/usr/bin/env bash
# PreToolUse(Bash) gate: run tests + validator scripts before any `git push`.
# Bound from .claude/settings.local.json. Exit 2 blocks the push and feeds
# stderr to Claude (exit 1 would NOT block — see the hooks contract).
set -uo pipefail

cmd=$(jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
grep -qE '(^|[^[:alnum:]_./-])git[[:space:]]+push([[:space:]]|$)' <<<"$cmd" || exit 0

# Used by scripts/test_claude_hooks.sh to verify matching without running tests.
[ "${RS_HOOK_DRY_RUN:-}" = "1" ] && exit 2

cd "${CLAUDE_PROJECT_DIR:?}"
{
  uv run pytest -n auto -x -q &&
  uv run python scripts/validate_imports.py &&
  uv run python scripts/validate_blocking_io.py &&
  uv run python scripts/validate_test_files.py &&
  uv run python scripts/validate_type_hints.py
} 1>&2 || { echo "BLOCKED: tests or validation scripts failed — fix before pushing." >&2; exit 2; }
exit 0
