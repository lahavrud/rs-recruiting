# frontend

Helm chart for the React SPA, deployed to the `rs-recruiting-sandbox` EKS
cluster (see `rs-recruiting-infra/tofu/sandbox`). Builds from
`frontend/Dockerfile.sandbox` — a separate image from the one prod uses
(`frontend/Dockerfile`, deployed to S3 + CloudFront): no TLS, no Cloudflare
config, just the Vite build baked into a plain-HTTP nginx image since the
cluster's Gateway/ALB terminates HTTP itself.

## Install

```bash
helm install frontend . \
  --namespace sandbox-staging --create-namespace \
  --set image.repository=<ECR_REPOSITORY_URL>/rs-recruiting-frontend \
  --set image.tag=<tag>
```

## Routing

Claims `/` (catch-all) on the cluster's shared Gateway (`sandbox` in
`kube-system`); the backend chart's HTTPRoute on the same Gateway claims the
more specific `/api`, `/auth`, `/health`, `/robots.txt`, `/sitemap.xml`
prefixes, so API calls from the SPA still resolve correctly via path
precedence even though frontend and backend are separate Deployments/Services.
