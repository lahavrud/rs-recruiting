#!/usr/bin/env bash
# PreToolUse(Bash) gate: run the repo linters before any `git commit`.
# Bound from .claude/settings.local.json. Exit 2 blocks the commit and feeds
# stderr to Claude (exit 1 would NOT block — see the hooks contract).
set -uo pipefail

input=$(cat)
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || exit 0
# Match `git commit` anywhere in the command (covers `cd x && git commit`).
grep -qE '(^|[^[:alnum:]_./-])git[[:space:]]+commit([[:space:]]|$)' <<<"$cmd" || exit 0

# Used by scripts/test_claude_hooks.sh to verify matching without running linters.
[ "${RS_HOOK_DRY_RUN:-}" = "1" ] && exit 2

# Lint the tree the commit actually runs in (repo root of the hook-input
# `cwd`), not the launch checkout — otherwise a commit from a
# .claude/worktrees/ worktree is blocked by unrelated dirty files in the main
# tree. Falls back to CLAUDE_PROJECT_DIR.
dir=$(jq -r '.cwd // empty' <<<"$input" 2>/dev/null)
root=$(git -C "${dir:-.}" rev-parse --show-toplevel 2>/dev/null)
cd "${root:-${CLAUDE_PROJECT_DIR:?}}"
{
  uv run ruff check . &&
  uv run ruff format --check . &&
  (cd frontend && npx tsc --noEmit && npm run lint)
} 1>&2 || { echo "BLOCKED: linters failed — fix the issues above before committing." >&2; exit 2; }
exit 0
