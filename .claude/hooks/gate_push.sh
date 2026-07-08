#!/usr/bin/env bash
# PreToolUse(Bash) gate: run tests + validator scripts before any `git push`
# that targets THIS repo. Pushes from other checkouts (e.g. the course repos)
# pass through — their own CI is their gate.
# Bound from .claude/settings.local.json. Exit 2 blocks the push and feeds
# stderr to Claude (exit 1 would NOT block — see the hooks contract).
set -uo pipefail

input=$(cat)
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
grep -qE '(^|[^[:alnum:]_./-])git[[:space:]]+push([[:space:]]|$)' <<<"$cmd" || exit 0

# Scope to this repo. The push runs in the session cwd unless the command
# cd's elsewhere first — take the last `cd` as the effective directory. Only
# skip the gate when that directory provably belongs to a DIFFERENT git repo;
# anything unresolvable stays gated (fail closed).
cwd=$(jq -r '.cwd // empty' <<<"$input" 2>/dev/null)
cdtarget=$(grep -oE '(^|[;&|])[[:space:]]*cd[[:space:]]+[^;&|]+' <<<"$cmd" | tail -1 |
  sed -E "s/^[;&|]?[[:space:]]*cd[[:space:]]+//; s/[[:space:]]+\$//; s/^\"(.*)\"\$/\\1/; s/^'(.*)'\$/\\1/")
dir=${cdtarget:-$cwd}
dir=${dir/#\~/$HOME}
if [ -n "$dir" ]; then
  case "$dir" in /*) ;; *) dir="${cwd:-${CLAUDE_PROJECT_DIR:?}}/$dir" ;; esac
  top=$(cd "$dir" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null)
  proj=$(cd "${CLAUDE_PROJECT_DIR:?}" && git rev-parse --show-toplevel 2>/dev/null || pwd)
  [ -n "$top" ] && [ "$top" != "$proj" ] && exit 0
fi

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
