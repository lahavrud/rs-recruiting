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
- Production deploys only happen via a pushed `vX.Y.Z` tag (`release.yml`), or a manual re-run of `deploy.yml`/`rollback.yml` for rollback. See `docs/release-process.md` for the full release ritual.

## CI/CD workflows (`.github/workflows/`)
- `ci.yml` — lint, test, docker-build (change-aware: docs-only PRs skip backend)
- `deploy-staging.yml` — manual. The only way an `-rc.N` tag gets created; computes the next RC version from commits since the last final tag and pushes it
- `cut-release.yml` — manual. Promotes an existing `-rc.N` tag to its final `vX.Y.Z` on the same commit — no rebuild, no bump arithmetic
- `release.yml` — triggered by tag push (`v*.*.*`). Builds & pushes the RC image; on a final tag, re-tags the existing image (no rebuild), deploys frontend + backend, creates the GitHub Release
- `deploy.yml` — manual only. Redeploys an already-built tag/SHA — rollback / escape hatch, not the normal release path
- `rollback.yml` — manual. Redeploys `PREV_SHA`
- `security-audit.yml` — weekly pip-audit for CVEs

Merging to `main` never deploys anything by itself — `main` is the only long-lived branch (trunk-based, no `develop`), and every deploy is gated behind an explicit tag push from one of the two manual "button" workflows above.

When editing workflows:
- Preserve the `detect-changes` job in `ci.yml` — it prevents unnecessary rebuilds
- OIDC permissions block must stay on any job that calls AWS (`id-token: write`, `contents: read`)
- Poll SSM run-command status after dispatch — never fire-and-forget
- `contents: write` is only granted to `deploy-staging.yml` and `cut-release.yml` — the only two workflows that push to the repo
- `deploy-staging.yml`/`cut-release.yml` explicitly run `gh workflow run release.yml --ref <tag>` after pushing a tag, instead of relying on `release.yml`'s push trigger — a tag pushed with the default `GITHUB_TOKEN` doesn't fire push-based workflow runs (GitHub's recursion-prevention rule). Don't remove the dispatch step as "redundant" with the push trigger.

## Infrastructure repo
Terraform/OpenTofu lives in a separate repo (`rs-recruiting-infra`). Do not modify infrastructure from this repo.

## Observability
- Sentry: backend DSN in SSM, frontend DSN in build args
- CloudWatch alarms → SNS `ops-alerts` topic
- Inspector2 scans ECR images on push
