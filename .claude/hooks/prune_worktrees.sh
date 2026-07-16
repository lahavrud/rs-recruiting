#!/usr/bin/env bash
# SessionStart (async): auto-prune stale agent worktrees under .claude/worktrees.
# A worktree is removed only when ALL of these hold:
#   - idle: its git admin HEAD file untouched for >7 days
#   - clean: no uncommitted changes
#   - auto-generated: branch name starts with "worktree-"
# The branch is then deleted only if merged (`git branch -d`, never -D), so
# commits are never lost. Stale worktrees that don't qualify are reported
# (SessionStart stdout becomes session context).
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:?}" || exit 0
root=".claude/worktrees"
[ -d "$root" ] || exit 0

leftover=0
for wt in "$root"/*/; do
  [ -e "${wt}.git" ] || continue
  gitdir=$(sed -n 's/^gitdir: //p' "${wt}.git" 2>/dev/null)
  [ -n "$gitdir" ] && [ -f "$gitdir/HEAD" ] || continue
  # idle >7 days? (HEAD mtime moves on any commit/checkout in the worktree)
  [ -n "$(find "$gitdir/HEAD" -mtime +7 2>/dev/null)" ] || continue
  if [ -n "$(git -C "$wt" status --porcelain 2>/dev/null)" ]; then
    leftover=$((leftover + 1)); continue
  fi
  branch=$(git -C "$wt" branch --show-current 2>/dev/null)
  case "$branch" in
    worktree-*) ;;
    *) leftover=$((leftover + 1)); continue ;;
  esac
  git worktree remove "$wt" >/dev/null 2>&1 || continue
  git branch -d "$branch" >/dev/null 2>&1 || true
done
git worktree prune >/dev/null 2>&1

if [ "$leftover" -gt 0 ]; then
  echo "Note: $leftover worktree(s) under .claude/worktrees are idle >7 days but dirty or manually named — worth a manual review."
fi
exit 0
