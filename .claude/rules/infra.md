# AWS & Infrastructure Rules

## Auth model
CI/CD uses OIDC — there are no stored AWS credentials anywhere in this repo. Never add `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` to GitHub secrets, `.env`, or any config file.

## Secrets
All secrets live in SSM Parameter Store as SecureStrings. To read a parameter locally:
```bash
aws ssm get-parameter --name "/rs-recruiting/<param>" --with-decryption
```
Never hardcode a value that should be in SSM. Never commit `.env` files that contain real credentials.

## Production safety
- Never run `alembic upgrade head` directly against the production database — the `_deploy.yml` migrate gate runs it as a one-off ECS task on the released image
- Production deploys only happen through `deliver.yml`'s **manual approval gate** (the `production` GitHub Environment's required reviewer), or a manual `rollback.yml` run. See `docs/release-process.md` for the full flow.
- An ECS rollback restores previous **app code only** — it does not undo a migration. Migrations must stay backward-compatible (expand now, contract a release later).

## CI/CD workflows (`.github/workflows/`)

Trunk-based **continuous delivery**: merge to `main` → CI green → build (by SHA) → staging → ⏸ manual approval → prod → tag `vX.Y.Z` + Release. `main` is the only long-lived branch (no `develop`).

- `ci.yml` — lint, test, docker-build (change-aware: docs-only PRs skip backend). A green run on a `push` to `main` is what triggers delivery.
- `deliver.yml` — triggered by `ci.yml` **completion** (`workflow_run`) for a `push` to `main` with `conclusion == success`. Builds base + api + worker + alloy (tagged by SHA, pushed to ops ECR), deploys staging, gates prod behind the approval, then tags + creates the GitHub Release. Triggering off CI completion (not raw push) means a commit only ships after its own tests pass.
- `_deploy.yml` — reusable (`workflow_call`), called by `deliver.yml` once per environment. Runs under `environment: <env>` (the production gate lives here — one job so there's one approval prompt). Steps: migrate gate (`alembic upgrade head` as a one-off ECS task derived from the live web task-def) → roll web → roll worker (both via the `ecs-roll` action) → frontend (S3 + CloudFront) → smoke check.
- `rollback.yml` — manual. Re-points an ECS service to its previous (or a pinned) task-def revision — break-glass, no rebuild.
- `security-audit.yml` — weekly pip-audit for CVEs.

Composite actions: `build-images` (base + api + worker + alloy → ops ECR), `ecs-roll` (render live task-def with new image + deploy via `aws-actions/amazon-ecs-*`, circuit breaker armed), `deploy-frontend` (build + S3 sync + CloudFront invalidation), `notify-failure` (open a GitHub issue).

When editing workflows:
- Preserve the `detect-changes` job in `ci.yml` — it prevents unnecessary rebuilds
- OIDC permissions block must stay on any job that calls AWS (`id-token: write`, `contents: read`)
- The production approval is a **GitHub Environment required reviewer** (`production` env, `main`-only), configured in repo settings — not in YAML. Don't try to encode it as a workflow step.
- Reusable-workflow secret names must be alphanumeric + underscore (no hyphens) — `_deploy.yml`'s `secrets:` use `ecs_role_arn`, `ops_ecr_registry`, etc.
- Keep the prod approval on a **single** job in `_deploy.yml` — multiple jobs referencing a protected environment each prompt for approval.

## Infrastructure repo
Terraform/OpenTofu lives in a separate repo (`rs-recruiting-infra`). Do not modify infrastructure from this repo.

The **persistent staging** cluster + RDS + OIDC deploy role live in the infra repo. Images are built once into the **ops account** ECR and pulled cross-account by both staging and prod. App-repo secrets the pipeline needs: `AWS_OPS_ECR_PUSH_ROLE_ARN` + `OPS_ECR_REGISTRY` (build), `AWS_STAGING_ECS_DEPLOY_ROLE_ARN` + `S3_FRONTEND_BUCKET_STAGING` + `CLOUDFRONT_DISTRIBUTION_ID_STAGING` (staging), `AWS_ECS_DEPLOY_ROLE_ARN` (var) + `AWS_ROLE_ARN` + `S3_FRONTEND_BUCKET` + `CLOUDFRONT_DISTRIBUTION_ID` + `VITE_SENTRY_DSN` (prod).

## Observability
- Sentry: backend DSN in SSM, frontend DSN in build args
- CloudWatch alarms → SNS `ops-alerts` topic
- Inspector2 scans ECR images on push
