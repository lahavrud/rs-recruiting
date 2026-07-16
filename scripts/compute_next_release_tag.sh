#!/usr/bin/env bash
# Compute the next vX.Y.Z release tag from Conventional Commits since the last
# final tag. Used by deliver.yml's tag-release job after a production deploy is
# approved — there are no -rc series and no hand-cut tags any more, the tag is a
# record of what shipped.
#
# Bump rules (highest wins) over commits in (LAST_FINAL..HEAD]:
#   - a `!` breaking marker or a `BREAKING CHANGE:` footer -> MAJOR
#   - any `feat` commit                                    -> MINOR
#   - anything else (fix/chore/docs/refactor/…)            -> PATCH
# If no final tag exists yet, seed at v0.1.0.
#
# I/O contract (mirrors the retired compute_next_*_tag.sh): progress to stderr,
# the bare tag to stdout for command substitution. Exits non-zero if the
# computed tag somehow already exists.
set -euo pipefail

LAST_FINAL=$(git tag --list 'v*.*.*' | grep -vE -- '-rc\.' | sort -V | tail -1 || true)

if [ -z "${LAST_FINAL}" ]; then
  echo "==> No final release tag exists yet — seeding at v0.1.0" >&2
  echo "v0.1.0"
  exit 0
fi
echo "==> Last final tag: ${LAST_FINAL}" >&2

RANGE="${LAST_FINAL}..HEAD"
SUBJECTS=$(git log --no-merges --format='%s' "${RANGE}")
BODIES=$(git log --no-merges --format='%B' "${RANGE}")

bump="patch"
if grep -qE '^[a-z]+(\([^)]*\))?!:' <<<"${SUBJECTS}" || grep -qE '^BREAKING CHANGE:' <<<"${BODIES}"; then
  bump="major"
elif grep -qE '^feat(\([^)]*\))?:' <<<"${SUBJECTS}"; then
  bump="minor"
fi
echo "==> Bump from commits in ${RANGE}: ${bump}" >&2

BASE_VERSION="${LAST_FINAL#v}"
MAJOR=$(echo "${BASE_VERSION}" | cut -d. -f1)
MINOR=$(echo "${BASE_VERSION}" | cut -d. -f2)
PATCH=$(echo "${BASE_VERSION}" | cut -d. -f3)

case "${bump}" in
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  patch) PATCH=$((PATCH + 1)) ;;
esac
TARGET="v${MAJOR}.${MINOR}.${PATCH}"

if git rev-parse -q --verify "refs/tags/${TARGET}" >/dev/null; then
  echo "==> Tag ${TARGET} already exists — aborting" >&2
  exit 1
fi
echo "==> Next release tag: ${TARGET}" >&2
echo "${TARGET}"
