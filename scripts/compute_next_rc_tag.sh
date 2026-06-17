#!/usr/bin/env bash
# Compute the next vX.Y.Z-rc.N tag for Deploy Staging.
#
# Walks commits since the last final tag (or starts at v0.1.0 if there is
# none), takes the highest-severity Conventional Commit type seen — a
# `release:major|minor|patch` label on the originating PR overrides a
# mistyped/missing commit prefix — bumps accordingly, then appends the
# next -rc.N suffix for that target version.
#
# Requires: GH_TOKEN, GITHUB_REPOSITORY (both already set in GitHub
# Actions). Prints the computed tag to stdout; all progress messages go
# to stderr so the tag can be captured cleanly via command substitution.
# Exits non-zero if there are no commits to release.
set -euo pipefail

LAST_FINAL=$(git tag --list 'v*.*.*' | grep -vE -- '-rc\.' | sort -V | tail -1 || true)

if [ -z "${LAST_FINAL}" ]; then
  # No prior release to diff a bump against — scanning all of history here would mean
  # one `gh api` call per commit ever made on main. Just start the series at v0.1.0.
  echo "==> No final tag yet — first tracked release, starting at v0.1.0" >&2
  TARGET="v0.1.0"
else
  BASE_VERSION="${LAST_FINAL#v}"
  echo "==> Last final tag: ${LAST_FINAL}" >&2

  COMMITS=$(git log "${LAST_FINAL}..HEAD" --format='%H')
  if [ -z "${COMMITS}" ]; then
    echo "==> No commits since ${LAST_FINAL} — nothing to release" >&2
    exit 1
  fi

  # Highest-severity Conventional Commit type wins. A `release:major|minor|patch`
  # label on the merged PR overrides a mistyped/missing commit prefix.
  SEVERITY="patch"
  while read -r SHA; do
    [ -z "${SHA}" ] && continue

    TYPE=""
    PR_JSON=$(gh api "repos/${GITHUB_REPOSITORY}/commits/${SHA}/pulls" --jq '.[0] // empty' 2>/dev/null || true)
    if [ -n "${PR_JSON}" ]; then
      LABEL=$(echo "${PR_JSON}" | jq -r '.labels[].name' | grep -E '^release:(major|minor|patch)$' | head -1 || true)
      [ -n "${LABEL}" ] && TYPE="${LABEL#release:}"
    fi

    if [ -z "${TYPE}" ]; then
      SUBJECT=$(git log -1 --format='%s' "${SHA}")
      if echo "${SUBJECT}" | grep -qE '^[a-z]+(\([a-z0-9_-]+\))?!:'; then
        TYPE="major"
      elif echo "${SUBJECT}" | grep -qE '^feat(\([a-z0-9_-]+\))?:'; then
        TYPE="minor"
      else
        TYPE="patch"
      fi
    fi

    case "${TYPE}" in
      major) SEVERITY="major" ;;
      minor) [ "${SEVERITY}" != "major" ] && SEVERITY="minor" ;;
    esac
  done <<< "${COMMITS}"
  echo "==> Computed severity: ${SEVERITY}" >&2

  MAJOR=$(echo "${BASE_VERSION}" | cut -d. -f1)
  MINOR=$(echo "${BASE_VERSION}" | cut -d. -f2)
  PATCH=$(echo "${BASE_VERSION}" | cut -d. -f3)
  case "${SEVERITY}" in
    major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
    minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
    patch) PATCH=$((PATCH + 1)) ;;
  esac
  TARGET="v${MAJOR}.${MINOR}.${PATCH}"
fi
echo "==> Target version: ${TARGET}" >&2

LAST_RC=$(git tag --list "${TARGET}-rc.*" | sort -V | tail -1 || true)
if [ -z "${LAST_RC}" ]; then
  N=1
else
  N=$(( $(echo "${LAST_RC}" | sed -E 's/.*-rc\.([0-9]+)$/\1/') + 1 ))
fi
RC_TAG="${TARGET}-rc.${N}"
echo "==> Next RC tag: ${RC_TAG}" >&2
echo "${RC_TAG}"
