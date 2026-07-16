#!/usr/bin/env bash
# PreToolUse(Edit|Write): auto-inject the matching .claude/rules/*.md file the
# first time a session edits a file in a rule-covered area. The path→rule map
# below mirrors the "Path-scoped rules" section of CLAUDE.md — keep them in sync.
set -uo pipefail

input=$(cat)
f=$(jq -r '.tool_input.file_path // empty' <<<"$input") || exit 0
sid=$(jq -r '.session_id // "nosession"' <<<"$input")
[ -n "$f" ] || exit 0

proj="${CLAUDE_PROJECT_DIR:-$(pwd)}"
rel="${f#"$proj"/}"

rule=""
case "$rel" in
  frontend/*)                                        rule=frontend ;;
  libs/shared/rs_shared/services/auth/*|services/api/rs_api/api/auth/*) rule=auth ;;
  alembic/*|libs/shared/rs_shared/models.py)         rule=migrations ;;
  libs/shared/rs_shared/core/tasks.py|libs/shared/rs_shared/core/task_contract.py|libs/shared/rs_shared/core/matching.py|services/worker/*) rule=worker ;;
  tests/*)                                           rule=tests ;;
  .github/workflows/*|scripts/*)                     rule=infra ;;
esac
[ -n "$rule" ] || exit 0

rulefile="$proj/.claude/rules/${rule}.md"
[ -f "$rulefile" ] || exit 0

# Inject each rule file at most once per session.
marker="${TMPDIR:-/tmp}/claude-rule-${sid}-${rule}"
[ -e "$marker" ] && exit 0
touch "$marker"

jq -n --rawfile rules "$rulefile" --arg rel "$rel" --arg rf ".claude/rules/${rule}.md" \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:("You are about to modify \($rel), which is covered by \($rf). Follow these rules:\n\n" + $rules)}}'
exit 0
