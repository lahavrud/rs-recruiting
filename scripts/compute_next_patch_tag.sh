#!/usr/bin/env bash
# Compute the next vX.Y.(Z+1) patch tag for an expedited Hotfix deploy.
#
# A hotfix is always a patch bump off the latest final tag — no commit
# scanning, no -rc series. Mirrors compute_next_rc_tag.sh's I/O contract:
# progress goes to stderr, the bare tag to stdout (so it can be captured via
# command substitution). Exits non-zero if no final tag exists yet (nothing
# to hotfix) or if the computed tag already exists.
set -euo pipefail

LAST_FINAL=$(git tag --list 'v*.*.*' | grep -vE -- '-rc\.' | sort -V | tail -1 || true)
if [ -z "${LAST_FINAL}" ]; then
  echo "==> No final release tag exists — nothing to hotfix" >&2
  exit 1
fi
echo "==> Last final tag: ${LAST_FINAL}" >&2

BASE_VERSION="${LAST_FINAL#v}"
MAJOR=$(echo "${BASE_VERSION}" | cut -d. -f1)
MINOR=$(echo "${BASE_VERSION}" | cut -d. -f2)
PATCH=$(echo "${BASE_VERSION}" | cut -d. -f3)
PATCH=$((PATCH + 1))
TARGET="v${MAJOR}.${MINOR}.${PATCH}"

if git rev-parse -q --verify "refs/tags/${TARGET}" >/dev/null; then
  echo "==> Tag ${TARGET} already exists — aborting" >&2
  exit 1
fi
echo "==> Next patch tag: ${TARGET}" >&2
echo "${TARGET}"
