#!/usr/bin/env bash
# PostToolUse(Edit|Write): auto-format the file that was just edited.
# Best-effort and always exits 0 — the commit/push gates and `make check`
# remain the enforcing layer; this just moves formatting feedback to edit time.
set -uo pipefail

f=$(jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -n "$f" ] && [ -f "$f" ] || exit 0

proj="${CLAUDE_PROJECT_DIR:-$(pwd)}"
case "$f" in
  "$proj"/*) ;;   # only touch files inside the project
  *) exit 0 ;;
esac

case "$f" in
  *.py)
    # --force-exclude honors pyproject excludes even for explicit paths
    (cd "$proj" && uv run ruff check --fix --force-exclude "$f" && uv run ruff format --force-exclude "$f") >/dev/null 2>&1
    ;;
  "$proj"/frontend/*.ts|"$proj"/frontend/*.tsx|"$proj"/frontend/*.css|"$proj"/frontend/*.json)
    (cd "$proj/frontend" && npx prettier --write --log-level silent "$f") >/dev/null 2>&1
    ;;
esac
exit 0
