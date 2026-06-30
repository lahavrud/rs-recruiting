# Release Process

Trunk-based **continuous delivery**. `main` is the only long-lived branch. Every
commit that lands on `main` and passes CI is built once and promoted to
production behind a single manual approval. There are no release-candidate tags
and no hand-cut version tags — the `vX.Y.Z` tag is created *after* a production
deploy, as a record of what shipped.

```
merge to main → CI green → build image (by SHA)
              → ⏸ manual approval → deploy PRODUCTION → tag vX.Y.Z + GitHub Release
```

> **Staging is retired** (cost). The pre-prod environment was on-demand
> scale-to-zero and didn't justify the moving parts, so the build is promoted
> straight to the production approval gate. The staging stage is preserved
> (commented) in `deliver.yml` and the reusable `_deploy.yml` is environment-
> agnostic, so re-enabling later is a config change, not a rewrite. Validate
> risky changes via CI + the prod gate + fast `rollback.yml`.

## The flow

1. **PR into `main`.** Feature branches go through the ruleset: CI green,
   code-owner review, squash merge with a Conventional Commit title.

2. **Build is automatic.** When CI passes on the merge commit, `deliver.yml`
   (triggered off CI *completion* for a `push` to `main`, so a commit only ships
   after its own tests are green) builds the base + api + worker + alloy images,
   tags them by commit SHA, and pushes to the **ops-account ECR**.

3. **Approve production.** The `deploy-prod` job runs under the `production`
   GitHub Environment, so it **pauses for a required reviewer**. Approve it in the
   run's UI (or the Environments page) to promote; reject it to abort. On approve,
   `_deploy.yml` runs: `alembic upgrade head` (gated) → roll web → roll worker
   (via `ecs-roll`) → frontend → smoke check.

4. **Tag + Release are automatic.** After prod deploys, `tag-release` computes the
   next `vX.Y.Z` from Conventional Commits since the last final tag
   (`scripts/compute_next_release_tag.sh`), tags the shipped commit, and creates a
   GitHub Release with generated notes.

## Backing out a bad change

- **Before you approve prod:** **reject** the pending deployment — nothing ships.
  Then `git revert` the bad commit on `main`; the next delivery rolls a clean
  build forward.
- **Already in production:** run **`rollback.yml`** (manual) — it re-points the
  ECS service(s) to the previous task-definition revision (seconds, no rebuild).
  Then `git revert` on `main` so git matches the deployed state and the next
  delivery doesn't re-ship the bad commit.
- **Hotfix** is not a separate path any more: merge the fix to `main` and approve
  prod quickly. The break-glass for an active incident is `rollback.yml`.

> ⚠️ A rollback restores previous **app code only** — it does **not** undo a
> database migration. Migrations must stay backward-compatible with the running
> version (**expand now, contract a release later**), or a rollback will run old
> code against a new schema. See `.claude/rules/migrations.md`.

## Workflow reference

| Workflow | Trigger | Does |
|---|---|---|
| `deliver.yml` | CI completion on `main` (push) | Build by SHA → ⏸ approval → prod → tag + Release (staging stage retired/commented) |
| `_deploy.yml` | `workflow_call` (from `deliver.yml`) | Migrate gate → roll web + worker (via `ecs-roll`) → frontend → smoke check, under `environment:` (env-agnostic; reusable for staging if re-enabled) |
| `rollback.yml` | Manual | Re-point an ECS service to its previous (or a pinned) task-def revision |
| `ci.yml` | PR / push / merge_group | Lint, test, docker-build (change-aware) |
| `security-audit.yml` | Weekly | pip-audit for CVEs |

## Manual approval setup (one-time)

The production gate is the **`production` GitHub Environment** with a required
reviewer (repo Settings → Environments), restricted to the `main` branch. These
are configured in repo settings, not in YAML. (A `staging` environment also
exists, kept for the eventual staging re-enable.)

## Environments & accounts

Production runs on ECS Fargate in its own AWS account; images are built once into
the **ops account** ECR and pulled cross-account. The deploy assumes a per-account
OIDC role (`rs-recruiting-prod-ecs-deploy`) — no stored AWS keys. Staging lives in
a separate account too but is **retired for now** (see the note at the top); its
infra (`rs-recruiting-staging` cluster, deploy role) lives in the infra repo
(`rs-recruiting-infra`) and should be destroyed there to actually stop charges —
disabling the workflow stage alone doesn't.

## Version bump detection

`compute_next_release_tag.sh` scans commits since the last final tag (each a
squashed PR with a Conventional Commit title) and takes the highest severity:

- any `!:` breaking-change marker or `BREAKING CHANGE:` footer → major
- `feat:` → minor
- everything else → patch

## Tag scope

One shared `vX.Y.Z` tag covers the backend image (API + worker run from the same
image with different `command:`) and the frontend bundle. They deploy together in
lockstep and share the same `VITE_RELEASE` / `SENTRY_RELEASE` value for Sentry
correlation — there's no independent release cadence to version separately.
