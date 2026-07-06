#!/usr/bin/env bash
# Self-test for the Claude Code guard-rail hooks in .claude/hooks/.
# Feeds real hook-input payloads and asserts block/allow behavior, so a hook
# that silently rots (wrong JSON field, wrong exit code) fails `make check`
# instead of failing open. Runs in <1s; no network, no repo mutation.
set -u

proj="$(cd "$(dirname "$0")/.." && pwd)"
hooks="$proj/.claude/hooks"
fail=0

t() { # t <expected_exit> <script> <json> <description>
  local want=$1 script=$2 json=$3 desc=$4
  printf '%s' "$json" | CLAUDE_PROJECT_DIR="$proj" bash "$hooks/$script" >/dev/null 2>&1
  local got=$?
  if [ "$got" -ne "$want" ]; then
    echo "FAIL: $desc (exit $got, expected $want)"
    fail=1
  fi
}

# --- pre_bash_guard.sh: migrations must not be applied by Claude -------------
t 2 pre_bash_guard.sh '{"tool_input":{"command":"uv run alembic upgrade head"}}' \
  "alembic upgrade without --sql is blocked"
t 2 pre_bash_guard.sh '{"tool_input":{"command":"cd /x && uv run alembic downgrade -1"}}' \
  "alembic downgrade without --sql is blocked"
t 0 pre_bash_guard.sh '{"tool_input":{"command":"uv run alembic upgrade --sql head"}}' \
  "alembic upgrade --sql (preview) is allowed"
t 0 pre_bash_guard.sh '{"tool_input":{"command":"uv run pytest -n auto"}}' \
  "unrelated command is allowed"

# --- gate_commit.sh / gate_push.sh: command matching (dry-run) ----------------
export RS_HOOK_DRY_RUN=1
t 2 gate_commit.sh '{"tool_input":{"command":"git commit -m x"}}' \
  "plain git commit triggers the lint gate"
t 2 gate_commit.sh '{"tool_input":{"command":"cd frontend && git commit -am x"}}' \
  "compound git commit triggers the lint gate"
t 0 gate_commit.sh '{"tool_input":{"command":"git log --oneline"}}' \
  "non-commit git command passes the lint gate"
t 2 gate_push.sh '{"tool_input":{"command":"git push origin feat/x"}}' \
  "git push triggers the test gate"
t 0 gate_push.sh '{"tool_input":{"command":"git pull origin main"}}' \
  "git pull passes the test gate"
unset RS_HOOK_DRY_RUN

# --- inject_rules.sh: rule injection fires once per session per rule ---------
sid="hooktest-$$"
rm -f "${TMPDIR:-/tmp}/claude-rule-${sid}-"*
out=$(printf '%s' "{\"session_id\":\"$sid\",\"tool_input\":{\"file_path\":\"$proj/tests/test_main.py\"}}" \
  | CLAUDE_PROJECT_DIR="$proj" bash "$hooks/inject_rules.sh" 2>/dev/null)
if ! grep -q '"additionalContext"' <<<"$out" || ! grep -q 'tests.md' <<<"$out"; then
  echo "FAIL: inject_rules did not inject tests.md for a tests/ edit"; fail=1
fi
out2=$(printf '%s' "{\"session_id\":\"$sid\",\"tool_input\":{\"file_path\":\"$proj/tests/test_main.py\"}}" \
  | CLAUDE_PROJECT_DIR="$proj" bash "$hooks/inject_rules.sh" 2>/dev/null)
if [ -n "$out2" ]; then
  echo "FAIL: inject_rules injected the same rule twice in one session"; fail=1
fi
out3=$(printf '%s' "{\"session_id\":\"$sid\",\"tool_input\":{\"file_path\":\"$proj/README.md\"}}" \
  | CLAUDE_PROJECT_DIR="$proj" bash "$hooks/inject_rules.sh" 2>/dev/null)
if [ -n "$out3" ]; then
  echo "FAIL: inject_rules fired for an unmapped path"; fail=1
fi
rm -f "${TMPDIR:-/tmp}/claude-rule-${sid}-"*

# --- prune_worktrees.sh: safe no-op outside a repo with agent worktrees -------
tmpproj=$(mktemp -d)
CLAUDE_PROJECT_DIR="$tmpproj" bash "$hooks/prune_worktrees.sh" >/dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "FAIL: prune_worktrees does not exit 0 when .claude/worktrees is absent"; fail=1
fi
rmdir "$tmpproj"

# --- format_on_edit.sh: never blocks ------------------------------------------
t 0 format_on_edit.sh '{"tool_input":{"file_path":"/nonexistent/file.py"}}' \
  "format hook exits 0 for a missing file"

if [ "$fail" -ne 0 ]; then
  echo "claude-hooks self-test: FAILED"
  exit 1
fi
echo "claude-hooks self-test: OK"
