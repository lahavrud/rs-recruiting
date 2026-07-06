#!/usr/bin/env bash
# PreToolUse(Bash): block applying migrations from Claude.
# Applying is a human step (see .claude/rules/migrations.md) — Claude may only
# preview with `alembic upgrade --sql`. Exit 2 blocks the call; stderr is fed
# to Claude (hooks contract: exit 0 = allow, exit 2 = block, anything else =
# NON-blocking — never "exit 1 to block").
set -uo pipefail

cmd=$(jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0

case "$cmd" in
  *"alembic upgrade"*|*"alembic downgrade"*)
    if [[ "$cmd" != *"--sql"* ]]; then
      echo "BLOCKED: applying/reverting migrations is a human step. Preview with 'uv run alembic upgrade --sql head' and ask the user to run the apply command themselves." >&2
      exit 2
    fi
    ;;
esac
exit 0
