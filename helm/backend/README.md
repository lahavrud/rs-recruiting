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
  --namespace sandbox-staging --create-namespace \
  --set image.repository=<ECR_REPOSITORY_URL>/rs-recruiting-backend \
  --set image.tag=<tag> \
  -f secrets.values.yaml
```

`env.allowedOrigins` / `env.frontendBaseUrl` default to `http://localhost:3000`
and need to be set to the Gateway's actual ALB hostname once known:

```bash
kubectl get gateway sandbox -n kube-system -o jsonpath='{.status.addresses[0].value}'
```

## Routing

The chart attaches an `HTTPRoute` to the cluster's shared Gateway
(`sandbox` in `kube-system`) for `/api`, `/auth`, `/health`, `/robots.txt`,
and `/sitemap.xml` — everything else falls through to the frontend chart's
route. `sandbox-staging` and `sandbox-prod` currently default to the same
paths on the one shared ALB; #20 needs to give each namespace a distinct
prefix (or hostname) before both can run side by side.

## Known gaps

- `autoscaling` (HPA) targets CPU utilization, which requires the
  `metrics-server` EKS addon. It isn't installed on the sandbox cluster yet,
  so the HPA will exist but report `<unknown>` until that's added.
- DB migrations are not run by this chart — out of scope per #17; the image's
  entrypoint is expected to run `alembic upgrade head` on startup.
