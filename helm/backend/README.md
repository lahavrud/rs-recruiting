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
  --set httpRoute.pathPrefix=/dev \
  -f secrets.values.yaml
```

`env.allowedOrigins` / `env.frontendBaseUrl` need to be set to the matching
CloudFront distribution's domain (see `rs-recruiting-infra`'s
`cloudfront_domain_names` output) for `sandbox-staging`/`sandbox-prod` —
CloudFront, not the ALB, is the public entry point for those. `sandbox-dev`
has no CloudFront in front of it (see Routing below); point a local
`npm run dev` frontend at the ALB hostname + `/dev` directly instead.

## Routing

The chart attaches an `HTTPRoute` to the cluster's shared Gateway
(`sandbox` in `kube-system`), one rule per `httpRoute.routes` entry
(`api`, `auth`, `health`, `robots.txt`, `sitemap.xml`), each matching
`{pathPrefix}/{route}`. When `pathPrefix` is non-empty, each rule also gets
a Gateway API `URLRewrite` filter that strips it back to the bare path
before forwarding — the app's routes are registered at `/api`, not
`/staging/api`, so without the rewrite every prefixed request 404s.
`TargetGroupConfiguration`'s health check always hits the bare `/health`
regardless of prefix, since health checks go straight to the
Service/pod and never pass through the HTTPRoute's rewrite.

The frontend's CloudFront distributions (`rs-recruiting-infra`'s `cdn.tf`)
forward `/api`, `/auth`, `/health`, `/robots.txt`, and `/sitemap.xml` to this
same ALB, prefixed per sub-environment so they don't collide on the one ALB:

| Namespace | CloudFront `origin_path` | This chart's `httpRoute.pathPrefix` |
|---|---|---|
| `sandbox-prod` | _(none)_ | _(none)_ — default, no override needed |
| `sandbox-staging` | `/staging` | `/staging` |
| `sandbox-dev` | _(no CloudFront)_ | `/dev` — set by hand, see Install above |

`sandbox-staging`/`sandbox-prod` get their override from the ArgoCD
Application's values overlay once #20 lands; `sandbox-dev` is never
ArgoCD-managed, so the override is just a `--set` on `helm install`.

## Known gaps

- `autoscaling` (HPA) targets CPU utilization, which requires the
  `metrics-server` EKS addon. It isn't installed on the sandbox cluster yet,
  so the HPA will exist but report `<unknown>` until that's added.
- DB migrations are not run by this chart — out of scope per #17; the image's
  entrypoint is expected to run `alembic upgrade head` on startup.
