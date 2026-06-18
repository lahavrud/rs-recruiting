# Release Process

Trunk-based, tag-gated releases. `main` is the only long-lived branch and never auto-deploys by itself — every deploy is triggered by pushing a semver tag, and tags only ever get created by clicking one of two workflow buttons.

## The ritual

1. **PR into `main`.** Feature branches go through the existing ruleset: CI green, code-owner review, squash merge with a Conventional Commit title.

2. **Click "Deploy Staging"** (`deploy-staging.yml`, optionally pinning a `ref` other than `main`). It computes the next release-candidate version from the commits since the last final tag, pushes `vX.Y.Z-rc.N`, then explicitly dispatches `release.yml`'s `build-rc` job against that tag (a `GITHUB_TOKEN`-authored push doesn't fire push-based workflows on its own, so the tag push alone wouldn't trigger it), which builds and pushes the image.

3. **Validate the RC.** (Staging deploy target lands with #890 — ephemeral staging environment.)

4. **If validation fails:** fix forward, merge more PRs into `main`, click **Deploy Staging** again. It re-scans commits since the last final tag, so if a `feat:` landed since the last RC the target version escalates correctly (e.g. `v1.3.0-rc.1` → `v1.4.0-rc.1`). Repeat until green.

5. **Once validated, click "Cut Release"** (`cut-release.yml`), pointing `rc_tag` at the validated RC (or leave blank for the most recent one). It strips the `-rc.N` suffix and pushes `vX.Y.Z` on the *same commit* — no rebuild, no bump arithmetic — then explicitly dispatches `release.yml`'s `promote-prod` job against that tag (same reason as step 2: the push alone doesn't trigger it): re-tag the existing RC image in ECR, deploy to EC2, deploy the frontend, and create the GitHub Release.

6. **Hotfix:** branch off `main`, PR back into `main` like any other change, click **Deploy Staging**, then immediately click **Cut Release**. Same two-button mechanism as a normal release — no special-casing, no back-merge, because there's only one branch.

7. **Rollback:** unchanged — `deploy.yml` (manual `workflow_dispatch` with a tag/SHA input) or `rollback.yml`. Both treat the deployed ref as an opaque string, so rolling back to a previous `vX.Y.Z` works the same as rolling back to a raw SHA.

## Workflow reference

| Workflow | Trigger | Does |
|---|---|---|
| `deploy-staging.yml` | Manual | Computes & pushes the next `vX.Y.Z-rc.N` tag |
| `cut-release.yml` | Manual | Promotes an existing RC tag to `vX.Y.Z` on the same commit |
| `release.yml` | Tag push (`v*.*.*`) | Builds the RC image; on a final tag, re-tags (no rebuild), deploys, creates the GitHub Release |
| `deploy.yml` | Manual | Redeploys an already-built tag or SHA — rollback / escape hatch |
| `rollback.yml` | Manual | Redeploys `PREV_SHA` |

## Version bump detection

`deploy-staging.yml` looks at every commit since the last final tag (each one is a single squashed PR with a Conventional Commit title) and takes the highest severity seen:

- `feat!:` / `fix!:` / any `!:` breaking-change marker → major
- `feat:` → minor
- everything else → patch

A `release:major` / `release:minor` / `release:patch` label on the originating PR overrides the parsed type — use it when a PR title was misclassified.

## Tag scope

One shared `vX.Y.Z` tag covers the backend image (API + worker, which run from the same image with different `command:`), and the frontend bundle. They already deploy together in lockstep and share the same `VITE_RELEASE` / `SENTRY_RELEASE` value for Sentry correlation — there's no independent release cadence to version separately.
