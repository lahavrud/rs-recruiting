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
- Never run `alembic upgrade head` directly against the production database
- Never SSH into the EC2 instance and run commands manually — use SSM Run Command
- Production deploys only happen via a pushed `vX.Y.Z` tag (`release.yml`, including the expedited `hotfix.yml` path), or a manual re-run of `deploy.yml`/`rollback.yml` for rollback. See `docs/release-process.md` for the full release ritual.

## CI/CD workflows (`.github/workflows/`)
- `ci.yml` — lint, test, docker-build (change-aware: docs-only PRs skip backend)
- `deploy-staging.yml` — manual. The only way an `-rc.N` tag gets created; computes the next RC version from commits since the last final tag and pushes it
- `cut-release.yml` — manual. Promotes an existing `-rc.N` tag to its final `vX.Y.Z` on the same commit — no rebuild, no bump arithmetic
- `hotfix.yml` — manual. Expedited prod hotfix: patch-bumps off the latest final tag and pushes `vX.Y.(Z+1)` straight to prod via `release.yml` — skips the RC + ephemeral-staging gate (incident-response path)
- `release.yml` — triggered by tag push (`v*.*.*`). RC tag: builds & pushes the image (prod ECR + mirrored to the staging-account ECR) and triggers the infra repo's `staging-apply.yml`. Final tag: re-tags the existing image (no rebuild), deploys frontend + backend, creates the GitHub Release, then triggers `staging-destroy.yml`
- `staging-deploy.yml` — `repository_dispatch` (`staging-provisioned`) from the infra repo's `staging-apply.yml`. Builds the frontend and SSM-deploys the RC to the ephemeral staging box (migrate + seed mock data; nginx serves the bundle). Staging is HTTP-only with no observability — it reuses `ssm-deploy` with `environment: staging` + a separate `deploy_ec2_staging.sh`/`docker-compose.staging.yml`/`nginx.staging.conf`
- `deploy.yml` — manual only. Redeploys an already-built tag/SHA — rollback / escape hatch, not the normal release path
- `rollback.yml` — manual. Redeploys `PREV_SHA`
- `security-audit.yml` — weekly pip-audit for CVEs

Merging to `main` never deploys anything by itself — `main` is the only long-lived branch (trunk-based, no `develop`), and every deploy is gated behind an explicit tag push from one of the manual "button" workflows above.

When editing workflows:
- Preserve the `detect-changes` job in `ci.yml` — it prevents unnecessary rebuilds
- OIDC permissions block must stay on any job that calls AWS (`id-token: write`, `contents: read`)
- Poll SSM run-command status after dispatch — never fire-and-forget
- `contents: write` is only granted to `deploy-staging.yml`, `cut-release.yml`, and `hotfix.yml` — the only workflows that push to the repo
- `deploy-staging.yml`/`cut-release.yml`/`hotfix.yml` explicitly run `gh workflow run release.yml --ref <tag>` after pushing a tag, instead of relying on `release.yml`'s push trigger — a tag pushed with the default `GITHUB_TOKEN` doesn't fire push-based workflow runs (GitHub's recursion-prevention rule). Don't remove the dispatch step as "redundant" with the push trigger.

## Infrastructure repo
Terraform/OpenTofu lives in a separate repo (`rs-recruiting-infra`). Do not modify infrastructure from this repo.

The **ephemeral staging** tofu lifecycle lives in the infra repo: `staging-apply.yml` / `staging-destroy.yml` / `staging-ttl-check.yml` (apply/destroy `tofu/staging-app` as a CI `tofu-provisioner` OIDC role; idle-expiry after 3 days). Cross-repo triggers (app↔infra) use a shared GitHub App (`CI_APP_ID` / `CI_APP_PRIVATE_KEY` secrets in both repos), because the default `GITHUB_TOKEN` can't dispatch workflows in another repo. App-repo secrets: `AWS_STAGING_DEPLOY_ROLE_ARN`, `STAGING_ECR_REGISTRY`.

## Observability
- Sentry: backend DSN in SSM, frontend DSN in build args
- CloudWatch alarms → SNS `ops-alerts` topic
- Inspector2 scans ECR images on push
