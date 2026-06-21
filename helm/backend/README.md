# backend

Helm chart for the FastAPI backend, deployed to the `rs-recruiting-sandbox`
EKS cluster (see `rs-recruiting-infra/tofu/sandbox`).

## Install

```bash
cat > secrets.values.yaml <<EOF   # gitignored — never commit this file
secrets:
  databaseUrl: "postgresql+asyncpg://..."
  jwtSecretKey: "$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
EOF

helm install backend . \
  --namespace sandbox-dev --create-namespace \
  --set image.repository=<ECR_REPOSITORY_URL>/rs-recruiting-backend \
  --set image.tag=<tag> \
  --set httpRoute.paths='{/dev/api,/dev/auth,/dev/health,/dev/robots.txt,/dev/sitemap.xml}' \
  -f secrets.values.yaml
```

`env.allowedOrigins` / `env.frontendBaseUrl` need to be set to the matching
CloudFront distribution's domain (see `rs-recruiting-infra`'s
`cloudfront_domain_names` output), not the ALB hostname directly — CloudFront,
not the ALB, is the public entry point now that the frontend deploys via
S3/CloudFront instead of an in-cluster chart.

## Routing

The chart attaches an `HTTPRoute` to the cluster's shared Gateway
(`sandbox` in `kube-system`). The frontend's CloudFront distribution
(`rs-recruiting-infra`'s `cdn.tf`) forwards `/api`, `/auth`, `/health`,
`/robots.txt`, and `/sitemap.xml` to this same ALB, prefixed per
sub-environment so all three can share the one ALB without colliding:

| Namespace | CloudFront `origin_path` | This chart's `httpRoute.paths` |
|---|---|---|
| `sandbox-prod` | _(none)_ | default (`/api`, `/auth`, ...) — no override needed |
| `sandbox-staging` | `/staging` | `/staging/api`, `/staging/auth`, ... |
| `sandbox-dev` | `/dev` | `/dev/api`, `/dev/auth`, ... — set by hand, see Install above |

`sandbox-staging`/`sandbox-prod` get their override from the ArgoCD
Application's values overlay once #20 lands; `sandbox-dev` is never
ArgoCD-managed, so the override is just a `--set` on `helm install`.

## Known gaps

- `autoscaling` (HPA) targets CPU utilization, which requires the
  `metrics-server` EKS addon. It isn't installed on the sandbox cluster yet,
  so the HPA will exist but report `<unknown>` until that's added.
- DB migrations are not run by this chart — out of scope per #17; the image's
  entrypoint is expected to run `alembic upgrade head` on startup.
