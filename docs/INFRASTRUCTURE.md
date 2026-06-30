# Infrastructure — Current State

The single source of truth for what's deployed in AWS, how it fits together, and *why* it was built this way. Every PR that touches infra updates this file in the same PR.

For higher-level architectural decisions (auth model, framework choices, etc.) see [`ARCHITECTURE.md`](./ARCHITECTURE.md). For operational runbooks see the doc pages listed at the bottom.

**Account:** `<ACCOUNT_ID>` · **Region:** `us-east-1` · **Created:** 2026-01-14

---

## 1. Topology

> ⚠️ **Superseded — pending audit.** Prod compute migrated from a single EC2 host
> to **ECS Fargate** (see the 2026-06-30 decisions-log entry). The EC2 host box,
> Elastic IP, security groups, and `GHA → SSM Run Command → EC2` deploy edges
> below describe the **pre-migration** state. The real ECS topology (cluster,
> services, task/execution roles, any ALB, log groups) lives in the infra repo /
> live AWS and has not yet been reconciled here. Section 2 (deploy pipeline) is
> current; this diagram is not.

```mermaid
flowchart LR
  User((User))
  CF["Cloudflare<br/>DNS only (grey-cloud)"]

  subgraph aws["AWS us-east-1"]
    subgraph cdn["CloudFront d2ghcom3efd3zg"]
      LE["Lambda@Edge<br/>viewer-request<br/>bot detection"]
      CFD["CloudFront distribution<br/>rs-recruiting.com + www<br/>ACM cert TLS"]
    end

    S3FE[("S3 bucket<br/>rs-recruiting-frontend<br/>SPA bundle · 3-day lifecycle")]

    subgraph vpc["VPC 10.0.0.0/16 (<VPC_ID>)"]
      subgraph ec2host["EC2 t3.micro<br/><EC2_INSTANCE_ID> (rs-server)<br/>EIP <ELASTIC_IP>"]
        api["api<br/>FastAPI<br/>port 8000"]
        worker["worker<br/>Arq"]
        redis["redis<br/>port 6379"]
        alloy["Grafana Alloy<br/>OTLP collector<br/>port 4317 (loopback)"]
      end
      RDS[("RDS Postgres 16<br/>rs-recruiting-prod-db<br/>db.t3.micro · single-AZ<br/>encrypted · 7d backups")]
    end

    S3A[("S3 bucket<br/>rs-recruiting-app<br/>versioning suspended · SSE-S3<br/>resumes + deploy artifacts")]
    ECR1[("ECR rs-recruiting/api<br/>IMMUTABLE · scanOnPush")]
    SSM[("SSM Parameter Store<br/>secrets + CURRENT_SHA")]
    CW["CloudWatch<br/>5 log groups, no retention set<br/>0 alarms · 0 dashboards"]
    GD["GuardDuty<br/>6h finding frequency"]
    CT["CloudTrail<br/>org trail · multi-region · log validation"]
  end

  subgraph mgmt["AWS Management Account (rs-admin)"]
    SNS1["SNS ops-alerts"]
    Budget["AWS Budget<br/>monthly-40<br/>50/80/100 actual + 100 forecast"]
    EBGD["EventBridge rule<br/>guardduty-findings"]
  end

  subgraph logsacct["AWS Logs Account (rs-logs-admin)"]
    S3CT[("S3 bucket<br/>rs-recruiting-org-trail-*<br/>versioned · SSE-S3 · BPA full")]
  end

  subgraph grafana["Grafana Cloud"]
    Loki["Loki<br/>logs"]
    Tempo["Tempo<br/>traces"]
    Mimir["Mimir<br/>metrics"]
    GrafanaDash["Grafana<br/>dashboards"]
    GrafanaSM["Synthetic Monitoring<br/>uptime checks"]
  end

  GHA["GitHub Actions<br/>OIDC role"]
  Sentry["Sentry"]
  Email["ops email"]

  User --> CF --> CFD
  CFD --> LE
  CFD -->|default behavior| S3FE
  CFD -->|"/api/* /auth/* /health"| api
  api --> redis
  api --> RDS
  worker --> redis
  worker --> RDS
  api --> S3A
  worker --> S3A
  api --> SSM
  worker --> SSM
  api -->|OTLP gRPC| alloy
  worker -->|OTLP gRPC| alloy
  alloy -->|traces| Tempo
  alloy -->|logs| Loki
  alloy -->|metrics| Mimir
  alloy -->|"CloudWatch metrics<br/>EC2 · RDS · SQS"| Mimir
  worker -->|"compliance logs<br/>/rs-recruiting/worker"| CW
  api -->|errors| Sentry
  worker -->|errors| Sentry
  Loki --> GrafanaDash
  Tempo --> GrafanaDash
  Mimir --> GrafanaDash

  GHA -->|push images| ECR1
  GHA -->|"s3 sync frontend bundle"| S3FE
  GHA -->|deploy artifacts| S3A
  GHA -->|run command| ec2host
  GHA -->|put CURRENT_SHA| SSM
  ec2host -->|pull images| ECR1
  ec2host -->|API calls audit| CT
  CT -->|deliver logs| S3CT
  GD -->|findings| EBGD
  EBGD --> SNS1
  SNS1 --> Email
  Budget -->|direct email, no SNS| Email
  GrafanaSM -->|"uptime checks<br/>(replaces R53 health-check alarm)"| CFD
  GrafanaSM -->|alerts| GrafanaDash
```

### Network notes

- **Single VPC** (`<VPC_ID>`); default VPC was deleted 2026-05-09.
- **No NAT Gateway, no ALB.** EC2 has an Elastic IP and reaches the internet via IGW. TLS terminates at CloudFront via ACM — EC2 only accepts HTTP :80 from the CloudFront managed prefix list.
- **CloudFront distribution** (`d2ghcom3efd3zg.cloudfront.net`) sits in front of both the S3 frontend bucket (default behavior) and EC2 (API behaviors). Lambda@Edge on the viewer-request event handles bot/crawler detection for OG prerendering.
- **DNS lives at Cloudflare** (grey-cloud, DNS only — proxying disabled). The only Route 53 resource is one health check (`<R53_HC_ID>`) — **orphaned**: the `rs-recruiting-uptime` CloudWatch alarm that used to consume it no longer exists. Uptime monitoring is now Grafana Cloud Synthetic Monitoring (`GRAFANA_SM_URL`/`GRAFANA_SM_ACCESS_TOKEN` in SSM). Candidate for deletion once SM is confirmed covering the same checks.
- **ACM certificate** (`arn:aws:acm:us-east-1:892512306022:certificate/d0e1d1f5-7bc9-41f8-9d81-98cb3786a626`) validated for `rs-recruiting.com` and `www.rs-recruiting.com`; attached to the CloudFront distribution.

### Security groups

| SG | Purpose | Ingress | Egress |
|---|---|---|---|
| `Web-SG` (`<WEB_SG_ID>`) | Public-facing on EC2 | `:80` from CloudFront managed prefix list (`com.amazonaws.global.cloudfront.origin-facing`), `:22` from `<ADMIN_IP>/32` | (default all-out) |
| `App-SG` (`<APP_SG_ID>`) | Inter-container on EC2 | `:8000` from Web-SG, `:6379` self-ref | `:443/80` to `0.0.0.0/0`, `:5432` to `0.0.0.0/0`, SMTP `:465/587` |
| `RDS-SG` (`<RDS_SG_ID>`) | RDS Postgres | `:5432` from App-SG | (default all-out) |
| `default` (`<DEFAULT_SG_ID>`) | VPC default — unused | (default self-ref) | (default all-out) |

Loose end: App-SG egress on `5432` is `0.0.0.0/0`; could be tightened to `RDS-SG` only. Tracked but not blocking.

---

## 2. Deploy pipeline

Trunk-based **continuous delivery** to ECS — see [`release-process.md`](./release-process.md) for the full flow and `.github/workflows/`.

Staging is retired for cost (the staging stage is preserved commented in
`deliver.yml`), so the build is promoted straight to the prod approval gate.

```mermaid
flowchart LR
  PR["merge to main"] --> CI["CI Pipeline (ci.yml)"]
  CI -->|"on success (workflow_run)"| DEL["deliver.yml"]
  DEL --> BUILD["build base+api+worker+alloy<br/>tagged by SHA"] --> ECR["ECR (ops account)<br/>IMMUTABLE · scanOnPush"]
  BUILD --> GATE{{"manual approval<br/>production environment"}}
  GATE -->|approve| PROD["deploy prod (_deploy.yml)<br/>migrate → roll web+worker → frontend"]
  PROD --> TAG["tag vX.Y.Z + GitHub Release"]
  ECR -->|"pull cross-account"| PROD
```

### Properties

- **Build once, by SHA:** base + api + worker + alloy images build a single time into the **ops-account** ECR (`IMMUTABLE`, `scanOnPush`), tagged by commit SHA, pulled cross-account by prod.
- **Gated migrations:** the prod deploy runs `alembic upgrade head` as a one-off ECS task derived from the live web task-def *before* rolling services; a failed migration aborts the roll and the old image keeps serving.
- **Manual prod gate:** the prod deploy runs under the `production` GitHub Environment (required reviewer, `main`-only).
- **Rollback:** `rollback.yml` re-points an ECS service to its previous (or a pinned) task-definition revision — **app code only**; migrations must be backward-compatible.
- **Ownership split:** Terraform/OpenTofu (infra repo) owns the ECS task-def *shape* (`ignore_changes = [task_definition]`); CI owns only the image tags.

---

## 3. Resource inventory

> ⚠️ **Superseded — pending audit.** The Compute, IAM, and SSM (`CURRENT_SHA`/
> `PREV_SHA`) rows below, and the Observability section's "Alloy on EC2" details,
> reflect the **pre-ECS** state. They were deliberately left rather than rewritten
> with invented ECS resource IDs (cluster ARNs, task/execution roles, log groups)
> that live in the infra repo and can't be verified from this repo. Audit against
> `rs-recruiting-infra` / live AWS and update in a follow-up. See the 2026-06-30
> decisions-log entry.

### Compute & data
| Resource | Identifier | Notes |
|---|---|---|
| CloudFront | `d2ghcom3efd3zg.cloudfront.net` | Custom domains: `rs-recruiting.com`, `www.rs-recruiting.com`. S3 default origin + EC2 API behaviors. Lambda@Edge viewer-request for bot detection. |
| ACM certificate | `arn:aws:acm:us-east-1:892512306022:certificate/d0e1d1f5-7bc9-41f8-9d81-98cb3786a626` | `us-east-1` (required for CloudFront). Covers apex + www. |
| EC2 | `<EC2_INSTANCE_ID>` (t3.micro) | IMDSv2 required, basic monitoring, in `App-SG` + `Web-SG`. Port 80 restricted to CloudFront prefix list. |
| EBS root | `<EBS_VOL_ID>` (8 GB gp3) | **Unencrypted** (pre-default-encryption); account-default now ON; one-shot re-encryption pending |
| Elastic IP | `<ELASTIC_IP>` (`<EIP_ASSOC_ID>`) | Attached to EC2 |
| RDS | `rs-recruiting-prod-db` (db.t3.micro) | Postgres 16, single-AZ, encrypted, 7d backup retention, deletion protection ON, Performance Insights 7d. **No CloudWatch log export enabled** (doc previously claimed postgresql log export — not configured) |
| Key pair | `rs-recruiting-key` | EC2 SSH key |

### Storage
| Bucket / repo | Purpose | Settings |
|---|---|---|
| `<APP_BUCKET>` | App data — resumes (`resumes/`), public assets (`public/*`), deploy artifacts (`deploy/${SHA}/`) | **Versioning SUSPENDED** (was ON; suspended 2026-05-13 — see decisions log). SSE-S3. BPA partial (public path allowed for BIMI logo). **Lifecycle:** noncurrent versions expire after 1d; delete markers auto-cleaned (`ExpiredObjectDeleteMarker: true`); abort incomplete multipart 7d. Deploy artifacts (`deploy/` prefix) expire after 30d (S3 lifecycle rule — CI does not prune; see decisions log 2026-05-09). |
| `rs-recruiting-frontend` | Frontend SPA bundle — CloudFront default-behavior origin | SSE-S3. **Lifecycle:** current versions expire after 3 days (stale bundle cleanup). CI syncs the new bundle and CloudFront serves from here; previous deploy's assets expire automatically. |
| `rs-recruiting-org-trail-*` | CloudTrail org-trail logs — **lives in the separate logs account (`rs-logs-admin`), not this account** | Versioning ON, SSE-S3, BPA full block |
| ECR `rs-recruiting/api` | Backend image | IMMUTABLE, scanOnPush, lifecycle "keep last 10 images" (manually applied — no IaC) |

### IAM
| Principal | Type | What it does |
|---|---|---|
| `rs-recruiting-prod-ec2-role` (instance profile `rs-recruiting-prod-ec2-profile`) | EC2 instance profile | Renamed from `rs-recruiting-app-role` during the #686 reorg. ECR pull, SSM read on `/rs-recruiting/prod/*` + `/rs-recruiting/infra/*` (write limited to `CURRENT_SHA`/`PREV_SHA`), S3 `GetObject`/`PutObject`/`DeleteObject`/`ListBucket` on the data bucket + read on the deploy bucket, SQS send/receive/delete on `rs-recruiting-tasks`, CW Logs write scoped to `/rs-recruiting/worker` only, `cloudwatch:GetMetricData`/`ListMetrics` (read-only, for Alloy's `prometheus.exporter.cloudwatch`). **No longer has `cloudwatch:PutMetricData`** — `RsRecruiting/Retention` namespace has zero metrics; the nightly `PurgedCandidatesCount` emit is likely broken. |
| `rs-recruiting-prod-github-actions` | GHA OIDC | Renamed from `github-actions-rs-recruiting`. CI: ECR push, S3 write to deploy prefix, SSM SendCommand + PutParameter on CURRENT_SHA |
| `rs-recruiting-prod-lambda-edge` | Lambda@Edge execution role | Bot-detection viewer-request function |
| `rs-recruiting-prod-scheduler` | Service role | Not yet documented — verify usage |
| `AWSDataLifecycleManagerDefaultRole` | Service | DLM weekly EC2 snapshot policy |

No IAM users remain in this account — `lahav-admin` was retired as part of the #686 reorg; human access is now via Identity Center (`lahav.rudik`, SSO).
Account password policy: 14-char, mixed, 90-day rotation, 5-prev reuse-prevent.
Default EBS encryption: ON (account-wide).

### Configuration
| Resource | Notes |
|---|---|
| SSM `/rs-recruiting/prod/*` | App secrets (DATABASE_URL, JWT_SECRET_KEY, SMTP_*, STORAGE_PROVIDER, GA4_*, etc.) — SecureString where appropriate. **Naming convention: parameter names are UPPERCASE**; the app loader lowercases them to match snake_case Pydantic field names. Keep new params UPPERCASE for operator clarity. The Grafana Cloud credentials below also live under this prefix, not `/rs-recruiting/infra/` as previously documented. |
| SSM `/rs-recruiting/infra/CURRENT_SHA`, `PREV_SHA` | String — current + previous deployed SHA (deploy version pointer + one-step rollback target for `scripts/rollback.sh`) |
| SSM `/rs-recruiting/prod/GRAFANA_LOKI_URL`, `GRAFANA_LOKI_USER` | SecureString — Grafana Cloud Loki push endpoint URL + numeric instance ID |
| SSM `/rs-recruiting/prod/GRAFANA_TEMPO_URL`, `GRAFANA_TEMPO_USER` | SecureString — Grafana Cloud Tempo OTLP endpoint URL + numeric instance ID |
| SSM `/rs-recruiting/prod/GRAFANA_PROMETHEUS_URL`, `GRAFANA_PROMETHEUS_USER` | SecureString — Grafana Cloud Mimir remote_write URL + numeric instance ID |
| SSM `/rs-recruiting/prod/GRAFANA_API_TOKEN` | SecureString — Grafana Cloud API token (scoped to Loki/Tempo/Mimir write) |
| SSM `/rs-recruiting/prod/GRAFANA_ORG_ID` | SecureString — Grafana Cloud org/stack ID |
| SSM `/rs-recruiting/prod/GRAFANA_SM_URL`, `GRAFANA_SM_ACCESS_TOKEN` | SecureString — Grafana Cloud Synthetic Monitoring API endpoint + access token (uptime checks, replaces the orphaned Route 53 health check + `rs-recruiting-uptime` alarm) |
| KMS | 2 customer-managed keys (default RDS + SSM) |
| Route 53 | 1 health check; no hosted zones (DNS at Cloudflare) |

### Observability

**Primary stack: Grafana Cloud (Loki / Tempo / Mimir) via Grafana Alloy on EC2.**

Grafana Alloy (`grafana/alloy:v1.5.1`) runs as a sidecar container. It exposes an OTLP gRPC receiver on `127.0.0.1:4317`. The api and worker containers ship all telemetry (traces, metrics, structured logs) via OTLP to Alloy, which fans out:

| Signal | Source | Destination |
|---|---|---|
| Traces | api + worker (OTLP) | Alloy → Grafana Cloud Tempo |
| App logs | api + worker (OTLP via `LoggingInstrumentor`) | Alloy → Grafana Cloud Loki |
| nginx logs | Docker socket tail (Alloy `loki.source.docker`) | Grafana Cloud Loki |
| App metrics | api + worker (OTLP) | Alloy → Grafana Cloud Mimir |
| AWS metrics | Alloy `prometheus.exporter.cloudwatch` (EC2 CPU/net, RDS CPU/conns/storage, SQS depth) | Grafana Cloud Mimir |
| Worker compliance logs | awslogs driver (parallel to OTLP) | CloudWatch `/rs-recruiting/worker` — **no retention policy set** (was documented as 400d; not actually configured) |

`otelTraceID` and `otelSpanID` are injected into every log record by `LoggingInstrumentor(set_logging_format=True)` in `telemetry.py`, enabling Loki → Tempo correlation. Sentry errors carry a `trace_id` tag (set in `RequestMiddleware`) that links to the same Tempo trace.

Credentials (`GRAFANA_LOKI_URL/USER`, `GRAFANA_TEMPO_URL/USER`, `GRAFANA_PROMETHEUS_URL/USER`, `GRAFANA_API_TOKEN`) are read from SSM by `deploy_ec2.sh` and injected as env vars into the Alloy container at startup.

**CloudWatch in the workload account — minimal, mostly orphaned:**

As of 2026-06-10, the workload account (`rs-recruiting` prod) has **zero CloudWatch alarms, zero dashboards, and zero metric filters**. Every alarm/dashboard/filter previously documented here (`ec2-cpu-high-rs-server`, `rds-cpu-high`, `rds-connections-high`, `rds-storage-low`, `rs-recruiting-uptime`, `retention-purge-stale`, `SecurityAlarm-CloudTrailChanges`, `nginx-5xx-rate-high`, `auth-*`, dashboard `rs-recruiting-ops`) is gone — confirmed via `cloudwatch describe-alarms` / `list-dashboards` / `describe-metric-filters` returning empty. These were not deliberately migrated one-for-one; they appear to have been dropped during the #686 account/IAM reorg and not recreated. Grafana Cloud (Mimir alerting + Synthetic Monitoring) is now the only active alerting layer for prod.

| Resource | Settings |
|---|---|
| Log group `/rs-recruiting/worker` | **No retention set** (documented as 400d — not configured). Compliance audit trail for `retention.purge candidate_id=` events (awslogs driver, parallel to OTLP). Only log group the EC2 role can still write to. |
| Log group `/rs-recruiting/api` | **No retention set.** Orphaned — IAM no longer grants write access (api logs route via OTLP only). Contains stale pre-migration data (~30KB). |
| Log group `/rs-recruiting/nginx` | **No retention set.** Orphaned — nginx logs route to Loki via Alloy's `loki.source.docker`. Contains stale pre-migration data (~1.7MB). |
| Log group `/aws/lambda/us-east-1.rs-recruiting-prod-bot-detection` | **No retention set.** Lambda@Edge function logs (AWS-managed, replicated per-region). |
| Log group `/aws/cloudfront/LambdaEdge/E2NPH508TQO0YO` | **No retention set.** CloudFront/Lambda@Edge access logs. |
| GuardDuty detector | ENABLED, **6h finding frequency** (was documented as 15-minute) |
| AWS RDS | **No CloudWatch log export enabled** (postgresql log export documented but not configured) |

**In the management account (`rs-admin`), not the workload account:**

| Resource | Settings |
|---|---|
| SNS `ops-alerts` | Email → ops address (confirmed). Consumer: EventBridge rule `guardduty-findings`. |
| EventBridge rule `guardduty-findings` | Pattern: `source=aws.guardduty, detail-type=GuardDuty Finding`. Target: `ops-alerts` SNS with input transformer that flattens raw JSON into a human-readable email (severity, type, title, description, region, resource type). Receives findings from the prod account's GuardDuty detector via the org delegated-admin setup. |
| AWS Budget `monthly-40` | $40/mo cost budget, **4 direct EMAIL subscriptions** (no SNS): 50%/80%/100% actual + 100% forecasted. ~$15.91 actual / ~$38.71 forecasted as of 2026-06-10. |

**CloudTrail:** the workload account's trail is `rs-recruiting-org-trail` (org-wide, multi-region, log file validation), delivering to a bucket in a separate logs account (`rs-logs-admin`, account ending `213059`) — not a same-account `rs-recruiting-cloudtrail-*` bucket as previously documented.

**Known gaps surfaced by this audit (not yet fixed — flagged for follow-up):**
- `/rs-recruiting/worker` has no retention policy, so the 400d compliance retention requirement for `retention.purge` audit logs is currently unmet.
- The EC2 role lost `cloudwatch:PutMetricData`; `RsRecruiting/Retention` namespace has zero datapoints, so the nightly `PurgedCandidatesCount` emit (`tasks.py::_emit_purge_count_metric`) is likely failing silently.
- The orphaned `/rs-recruiting/api` and `/rs-recruiting/nginx` log groups (and the two AWS-managed Lambda/CloudFront groups) have no retention and accrue storage cost indefinitely.
- The Route 53 health check is unused (see Network notes above) — candidate for deletion once Grafana Synthetic Monitoring coverage is confirmed equivalent.

### Backup posture
| Layer | Mechanism | Retention |
|---|---|---|
| RDS | Automated daily snapshot | 7 days |
| EC2 root EBS | DLM policy `<DLM_POLICY_ID>` weekly | Last 4 |
| S3 (app bucket) | Versioning suspended — new writes get null version; `delete_file` purges all versions + markers explicitly | N/A (versioning off for new objects; lifecycle expires orphaned noncurrent versions within 1d) |
| S3 (CloudTrail bucket, `rs-logs-admin` account) | Versioning | All versions kept |

### Custom metrics namespace
| Namespace | Metric | Source | Status |
|---|---|---|---|
| `RsRecruiting/Retention` | `PurgedCandidatesCount` | Worker — Arq cron, see `tasks.py::_emit_purge_count_metric` | **Broken** — namespace has zero datapoints; EC2 role lacks `cloudwatch:PutMetricData` (see Known gaps above) |
| `RsRecruiting/Auth` | `LoginFailedCount`, `AccountLockedCount`, `LockoutHitCount`, `RateLimitHitCount` | API — structured log events via CloudWatch metric filters | **Removed** — backing metric filters and alarms no longer exist; auth events are still logged structurally and route to Loki via OTLP, but no CloudWatch/Grafana alert currently watches them |

---

## 4. Decisions log (append-only)

Newest first. Each entry: date, what, why, links. When updating, append; don't rewrite history.

### 2026-06-30 — Migrate prod compute EC2 → ECS Fargate; CI/CD → continuous delivery
**Decision:** Rebuilt the app repo's CI/CD for ECS (see [`release-process.md`](./release-process.md)): `deliver.yml` (build-by-SHA → manual approval → prod → auto-tag) + a reusable `_deploy.yml` + an `ecs-roll` composite action, replacing the tag-gated EC2/SSM flow. Deleted `release.yml`, `deploy.yml`, `deploy-staging.yml`, `cut-release.yml`, `hotfix.yml`, `staging-deploy.yml`, the `ssm-deploy` action, the `compute_next_{rc,patch}_tag.sh` scripts, and the EC2 `deploy_ec2*.sh` / `rollback.sh` / `validate_deploy_artifacts.sh` scripts + `docker-compose.{deploy,staging}.yml` + `nginx.staging.conf`. Prod runs on ECS Fargate (`rs-recruiting-prod` cluster, `-web` / `-worker` services, alloy sidecar, behind an ALB; CloudFront → ALB; Route53 zone for `rs-recruiting.com` in the prod account); images build once into the **ops-account** ECR and are pulled cross-account. The production gate is a GitHub Environment required reviewer; `rollback.yml` re-points a service to its previous task-def revision. **Staging was built (separate account `788572612917`, Fargate-Postgres / no-ALB / all-Spot scale-to-zero) but retired from the pipeline for cost** — the staging stage is preserved commented in `deliver.yml` for later re-enable; its tofu units should be destroyed in `rs-recruiting-infra` to actually stop charges.
**Why:** Continuous delivery on merge with a single manual prod gate — no hand-cut RC/version tags, no SSH/SSM deploy machinery, no ephemeral-staging tofu dance. The `vX.Y.Z` tag becomes a *record* of what shipped (auto-created after a prod deploy), not a deploy trigger. Staging's value (UI/real-env validation) didn't justify the standing cost for a solo/trunk-based repo with a manual prod gate + fast rollback.
**Names verified against `rs-recruiting-infra`:** cluster `rs-recruiting-prod`, services/families `rs-recruiting-prod-{web,worker}`, containers `web`/`worker` + `alloy` sidecar, log group `/ecs/rs-recruiting-prod-<suffix>`, deploy role `rs-recruiting-prod-ecs-deploy` (trusts `repo:lahavrud/rs-recruiting:*`), frontend role `rs-recruiting-prod-frontend-deploy`, ops ECR push role. Prod accounts: prod `892512306022`, ops (ECR), mgmt `510144817435`.
**⚠️ Doc debt — NOT yet reconciled:** Sections 1 (Topology) and 3 (Resource inventory — Compute/IAM/SSM) and the Observability section still describe the **pre-migration EC2 state** (EC2 instance + EIP, `Web-SG`/`App-SG`, `rs-recruiting-prod-ec2-role`, `CURRENT_SHA`/`PREV_SHA` SSM params, Alloy-on-EC2). The ECS/ALB/Route53 resource IDs live in `rs-recruiting-infra` (now the source of truth, mid `feat/retire-legacy-prod`) and should be folded into the inventory tables in a follow-up.

### 2026-06-10 — Audit: doc vs. reality reconciliation post-#686 reorg + Grafana migration
**Decision:** No infra changes — this is a documentation correction. Audited the prod account (`rs-prod-admin`) plus the management (`rs-admin`), security (`rs-security-admin`), and logs (`rs-logs-admin`) accounts via CLI and found the "CloudWatch — retained for compliance and alarms only" section (last touched 2026-06-05) no longer matched reality. The 9 documented alarms, the `rs-recruiting-ops` dashboard, and all 5 metric filters do not exist anywhere in the org — `describe-alarms`/`list-dashboards`/`describe-metric-filters` all return empty in the prod account. `ops-alerts` SNS and the `monthly-40` budget exist, but in the management account, not the workload account. The `rs-recruiting-app-role`/`github-actions-rs-recruiting` IAM principals were renamed to `rs-recruiting-prod-ec2-role`/`rs-recruiting-prod-github-actions` (with `rs-recruiting-prod-lambda-edge` and `rs-recruiting-prod-scheduler` added) and the `lahav-admin` IAM user is gone (Identity Center now). CloudTrail is now an org trail delivering to a bucket in the separate logs account. GuardDuty's finding frequency is 6h (not 15min). Grafana Cloud Synthetic Monitoring credentials exist in SSM under `/rs-recruiting/prod/GRAFANA_SM_*`, replacing the orphaned Route 53 health check + `rs-recruiting-uptime` alarm. Updated the topology diagram, resource inventory, IAM table, SSM table, and observability section to match.
**Why:** This doc is the source of truth per the maintenance rules, but had drifted significantly — almost certainly because the #686 account/IAM reorg and the 2026-06-05 Grafana cutover both touched this area without a follow-up doc pass once the dust settled.
**New gaps surfaced (not yet fixed):** `/rs-recruiting/worker` has no retention policy (compliance requirement is 400d); `RsRecruiting/Retention` → `PurgedCandidatesCount` is likely failing silently (EC2 role lost `cloudwatch:PutMetricData`); orphaned `/rs-recruiting/api` and `/rs-recruiting/nginx` log groups (plus 2 AWS-managed Lambda/CloudFront groups) have no retention. See "Known gaps" in the Observability section.

### 2026-06-10 — Fix: API logs never reached Loki (issue [#862](https://github.com/lahavrud/rs-recruiting/issues/862))
**Decision:** Reorder `src/main.py` so `configure_telemetry("rs-recruiting-api")` runs *after* `_configure_logging()`, matching `src/worker.py`'s order.
**Why:** While investigating the 2026-06-10 outage in Grafana Cloud Loki, the `service_name` label browser showed `nginx`, `rs-recruiting-uptime`, and `rs-recruiting/rs-recruiting-worker` — but **no `rs-recruiting/rs-recruiting-api`**, ever. `configure_telemetry()` (via `LoggingInstrumentor().instrument()`) adds an OTel `LoggingHandler` to the root logger, bridging stdlib `logger.*` calls to the OTLP log exporter → Alloy → Loki. `_configure_logging()` then ran `root.handlers = [handler]`, replacing the handler list and silently dropping that OTel handler — so API logs only ever went to stdout/CloudWatch, never to Loki. `worker.py` happened to call the two functions in the opposite order and was unaffected.
**Trade:** None — straightforward ordering fix. Until this deploys, API logs for any incident (including this one) are only in CloudWatch/stdout, not Loki/Tempo-correlated.

### 2026-06-10 — Persist Alloy's loki.write WAL across reboots (issue [#862](https://github.com/lahavrud/rs-recruiting/issues/862))
**Decision:** Enable the `wal` block on the `loki.write "grafana_cloud"` component in `alloy/config.alloy`, and run Alloy with `--storage.path=/var/lib/alloy/data` backed by a new named Docker volume (`alloy-data`) in `docker-compose.deploy.yml`.
**Why:** During the 2026-06-10 prod outage (api/worker hang → EC2 reboot to recover), logs from the minutes leading up to the hang were missing from Grafana Cloud Loki. Loki itself has been externally hosted on Grafana Cloud since 2026-06-05 (durable by default), but `loki.write` buffers entries in memory before pushing — a hard reboot drops anything still queued. The WAL persists that queue to disk so a restarted Alloy resumes sending instead of losing it.
**Trade:** Slightly higher disk usage on the EC2 root volume for the WAL segments (bounded by `max_segment_age`, default 1h). Doesn't cover the separate, smaller in-process buffer in the api/worker's `BatchLogRecordProcessor` (`telemetry.py`) — a hard kill can still drop the last few seconds of logs that never reached Alloy at all; out of scope for this issue.

### 2026-06-05 — Grafana Cloud observability stack: Alloy → Loki / Tempo / Mimir
**Decision:** Replace CloudWatch as the primary log/metric/trace backend with Grafana Cloud. Grafana Alloy (`v1.5.1`) runs as a sidecar container on EC2 and receives all telemetry from the api and worker containers via OTLP gRPC (port 4317 on loopback). Alloy fans out: traces → Grafana Cloud Tempo, structured logs → Grafana Cloud Loki, app metrics → Grafana Cloud Mimir, and AWS native metrics (EC2/RDS/SQS) scraped from CloudWatch → Mimir. nginx container logs are tailed from the Docker socket directly into Loki. The Python `LoggingInstrumentor(set_logging_format=True)` injects `otelTraceID`/`otelSpanID` into every log record for Loki→Tempo deep linking. `RequestMiddleware` sets a Sentry `trace_id` tag from the active OTel span so Sentry errors can be correlated to Tempo traces. Worker logs ship dual-path: OTLP → Loki (primary) and awslogs driver → CloudWatch `/rs-recruiting/worker` (compliance, 400d retention). CloudWatch alarms backed by now-dead metric filters (`nginx-5xx-rate-high`, `auth-*`) remain in AWS but are no-ops — cleanup tracked in the observability table above.
**Why:** CloudWatch Logs Insights is expensive at scale and query ergonomics are poor. Grafana Cloud free tier covers current traffic. Tempo provides distributed tracing that CloudWatch never offered. A single Grafana dashboard correlating logs, traces, and metrics (including AWS-native metrics) replaces four separate AWS consoles.
**Trade:** Grafana Cloud credentials (API token + per-datasource URLs) in SSM — one more secret to rotate. Alloy adds a container to the deploy compose; if Alloy crashes, OTLP telemetry is lost until it restarts (worker compliance logs are still safe in CloudWatch via the awslogs path). Existing CloudWatch alarms for EC2/RDS/uptime are kept as a fallback since those signals don't depend on log ingestion.

### 2026-06-04 — CloudFront + S3 frontend; custom domain via ACM (PR [#723](https://github.com/lahavrud/rs-recruiting/pull/723), infra PR [#1](https://github.com/lahavrud/rs-recruiting-infra/pull/1))
**Decision:** Replace direct EC2 serving with a CloudFront distribution. Frontend SPA is now served from a dedicated S3 bucket (`rs-recruiting-frontend`, 3-day lifecycle). API traffic (`/api/*`, `/auth/*`, `/health`) continues to hit EC2, but now via CloudFront as an origin — no direct public exposure. Lambda@Edge viewer-request function handles bot/crawler detection and routes to the FastAPI OG prerender endpoint. TLS terminates at CloudFront via an ACM certificate (`us-east-1`) covering apex and www. EC2 port 443 (nginx TLS) is replaced by port 80 restricted to the CloudFront managed prefix list. Cloudflare DNS set to grey-cloud (DNS only) — proxying disabled so CloudFront handles its own TLS handshake. Custom domains wired as CloudFront aliases: `rs-recruiting.com` and `www.rs-recruiting.com`.
**Why:** nginx TLS on EC2 required storing a cert+key in SSM and materializing it on every deploy — rotating it was manual. ACM auto-renews. S3 for the SPA removes the EC2 as a static-asset bottleneck, drops one concern from the EC2 deploy (no more `nginx.conf` in the image), and adds a CDN cache layer. CloudFront also gives us a single consistent TLS endpoint for both frontend and API, and Lambda@Edge bot detection runs at the edge rather than on every EC2 request.
**Trade:** CloudFront adds ~$0.50–1/mo in CDN costs at current traffic (negligible). Lambda@Edge adds ~1ms viewer-request latency. The frontend bucket's 3-day lifecycle means a rollback window of 3 days; beyond that the old bundle is gone (acceptable — we can re-deploy any SHA from ECR history). Cloudflare proxying disabled — lose Cloudflare's DDoS scrubbing; CloudFront's WAF/Shield Standard replaces it.

### 2026-05-20 — Auth observability: structured log events, split metrics, brute-force alarm
**Decision:** Added structured log events across the auth surface: `login_failed`, `login_account_locked`, `login_lockout_hit`, `login_email_not_found`, `login_success`, `rate_limit_hit` (all with `ip` field), `password_reset_token_invalid`, `registration_email_exists`. Fixed `request_id` correlation ID to appear in every JSON log line (`fmt` fix). Split the old combined `LoginFailureCount` metric filter into four distinct signals (`LoginFailedCount`, `AccountLockedCount`, `LockoutHitCount`, `RateLimitHitCount`) under `RsRecruiting/Auth`. Added alarm `auth-login-failed-spike` (> 10 in 5 min). Updated `rs-recruiting-ops` dashboard auth panel to show all four series. Added `RateLimitExceeded` exception handler that logs and returns clean JSON 429.
**Why:** Login failures had no IP, no correlation ID, and conflated three distinct attack signals into one metric. Rate limit hits were invisible. The dashboard showed a single number with no way to distinguish brute-force from distributed stuffing from legitimate lockouts.
**Trade:** `login_email_not_found` is always logged internally but the HTTP response remains identical to `login_failed` — no user-facing information leak. Rate-limit logging only fires in production (limiter is disabled in dev/test per `limiter.py`).

### 2026-05-20 — Rename CW metric namespaces RsRecruitment → RsRecruiting
**Decision:** Renamed both custom CloudWatch metric namespaces to match the correct brand name: `RsRecruitment/Retention` → `RsRecruiting/Retention` and `RsRecruitment/Nginx` → `RsRecruiting/Nginx`. Updated IAM inline policy `CloudWatchPutRetentionMetric` condition on `rs-recruiting-app-role` to allow `RsRecruiting/Retention`. Updated `retention-purge-stale` and `nginx-5xx-rate-high` alarms, `rs-recruiting-ops` dashboard, `nginx-5xx-errors` metric filter, `tasks.py` `METRIC_NAMESPACE` constant.
**Why:** All other brand-visible naming uses "RS Recruiting"; the old namespace string was a copy-paste of the repo slug rather than the brand name.
**Trade:** Brief window between alarm update and next worker cron run (~0–26h) where `retention-purge-stale` may fire once, then self-recover on the first nightly emit to the new namespace.

### 2026-05-20 — 5xx alarm, RDS log retention, ops dashboard (PRs #587 #595 #596)
**Decision:** (1) Added CloudWatch metric filter `nginx-5xx-errors` on `/rs-recruiting/nginx` using the nginx combined-log field-extraction pattern (`status=5*`), emitting `RsRecruiting/Nginx / Http5xxCount`. Created alarm `nginx-5xx-rate-high` at Sum > 5 per 5-min window → `ops-alerts`. (2) Set 30d retention on the RDS log group `/aws/rds/instance/rs-recruiting-prod-db/postgresql` (was indefinite). (3) Created dashboard `rs-recruiting-ops` with 5 metric panels and 4 saved Logs Insights queries.
**Why:** A 500 storm on any business endpoint would not have fired any existing alarm (Route53 health check only pings `/health`). RDS log group was the only log group without a retention policy, creating unbounded cost risk. Dashboard reduces mean-time-to-orient when `ops-alerts` fires.
**Trade:** Alarm threshold of 5 per 5 min is intentionally generous for a low-traffic job board — avoids noise from transient deploys. Lockout-rate dashboard panel deferred pending #588.

### 2026-05-13 — Permanent S3 file deletion + versioning suspended (PR [#406](https://github.com/lahavrud/rs-recruiting/pull/406))
**Decision:** (1) Suspend S3 versioning on the app bucket. (2) Add lifecycle rule: noncurrent versions expire after 1 day, delete markers auto-cleaned. (3) Update `S3StorageProvider.delete_file` to walk `list_object_versions` and call `delete_objects` with explicit VersionIds, permanently removing every version and marker rather than creating a new delete marker. (4) Extend `rs-recruiting-app-role` S3 policy with `s3:DeleteObjectVersion` and `s3:ListBucketVersions`.
**Why:** With versioning enabled, `delete_object` only inserts a delete marker — the actual object data remains. A live test confirmed that deleting a candidate left their resume version in S3 (observable via `list_object_versions`). Since all file keys include a UUID (no overwrite risk), versioning bought nothing for the app while making every delete a multi-step operation. Suspension + code-level permanent delete satisfies the 12-month retention policy's "data is gone" guarantee. Lifecycle rule is the safety net for any marker or version that pre-dates this change.
**Trade:** Can't fully disable versioning once enabled (AWS limitation) — suspension is the equivalent. The permanent-delete code path (version walk + `delete_objects`) is slightly more complex than a plain `delete_object` call, but remains correct on both suspended and fully-versioned buckets.

### 2026-05-09 — GuardDuty enabled, findings → ops-alerts via EventBridge transformer
**Decision:** Enable GuardDuty (15-minute publishing frequency, 30-day free trial), wire findings to the existing `ops-alerts` SNS topic via an EventBridge rule with an input transformer that flattens the raw finding JSON into a readable email summary (severity, type, title, description, region, resource type).
**Why:** CloudTrail is now writing API audit data, but no human reads CloudTrail manually. GuardDuty turns CloudTrail (+ DNS + EC2 metadata) into actionable signal — primarily catches credential abuse, which is the realistic threat at single-admin scale. The 30-day trial gives a real cost estimate before committing; if it lands above ~$5/mo or generates noise, can disable.
**Trade:** added one EventBridge rule + one new statement on the SNS topic policy (allow `events.amazonaws.com` to publish). VPC Flow Logs explicitly skipped — see prior entry.

### 2026-05-09 — Billing alerts via AWS Budget only; S3 lifecycle + cleanup
**Decision:** Delete the redundant CloudWatch `billing-over-40` alarm and `billing-alerts` SNS topic. AWS Budget `monthly-40` already has 4 direct EMAIL subscriptions (50%/80%/100% actual + 100% forecasted) that fire faster and with finer-grained thresholds than the alarm — keeping both was duplicate notifications. Net: one fewer alarm, one fewer SNS topic, only `ops-alerts` remains. Also cleaned up obsolete root-level S3 deploy artifacts (`deploy/{deploy_ec2.sh, docker-compose.deploy.yml, nginx.conf, dist/, seed_admin.py}` — all leftovers from the pre-#296 deploy model) and applied a lifecycle policy: `deploy/` current versions expire after 30 days (matches the spirit of ECR's "keep last 10 tagged" since deploys land near-daily), global noncurrent versions expire after 30 days, incomplete multipart uploads abort after 7 days.
**Why:** Surfaced when reviewing the topology diagram — billing alerts appeared to flow through SNS, but the actual budget mechanism is direct email. Same review caught that the bucket still had pre-atomic-deploy artifacts at the root level that nothing reads anymore.

### 2026-05-09 — GuardDuty over VPC Flow Logs
**Decision:** Enable GuardDuty (with EventBridge → ops-alerts), defer Flow Logs.
**Why:** At single-EC2 + Cloudflare-fronted scale, Flow Logs would be mostly noise from internet port-scans; the realistic incident response is "rotate keys, restore backup," not network forensics. GuardDuty fills the credential-leak detection gap that CloudTrail alone can't (no one reads CloudTrail manually).
**Trigger to revisit Flow Logs:** add a second EC2, NAT gateway, or land an enterprise customer requiring it.

### 2026-05-09 — CloudTrail in dedicated bucket
**Decision:** Multi-region trail with log file validation, in a separate dedicated bucket (BPA full block, versioning).
**Why:** Audit logs deserve a separate access boundary from app data. Dedicated bucket means a misconfigured S3 lifecycle on the app bucket can't expire audit logs.

### 2026-05-09 — Day 1 + Day 2 hardening
**Decision:** Delete `rs-app-dev` long-lived IAM key + wildcard policies; password policy; default EBS encryption; ECR `IMMUTABLE` + `scanOnPush`; alarm routing to `ops-alerts` (billing kept on `billing-alerts`); RDS Performance Insights + log exports; worker log retention 14→400 days; delete default VPC + orphan SGs.
**Why:** AWS audit pre-Day 3. Detail in this conversation; resource state above reflects post-change.
**Side-effect PR:** [#301](https://github.com/lahavrud/rs-recruiting/pull/301) dropped `:latest` push from CI to enable `IMMUTABLE`.

### 2026-05-09 — Audit log: DB-only with INSERT-only grants (Phase 1); S3 Object Lock deferred (Phase 2)
**Decision:** Keep PR [#300](https://github.com/lahavrud/rs-recruiting/pull/300)'s DB table as the source of truth. Add INSERT-only grants for the app role (issue [#303](https://github.com/lahavrud/rs-recruiting/issues/303), Phase 1). Defer S3 Object Lock + Firehose archive (Phase 2) until enterprise/regulator triggers it.
**Why not CloudWatch-only:** loses transactional consistency with the business operation — silent compliance gaps under failure. **Why not Object Lock today:** permanent commitment, ~1 day of work, no auditor asking right now.

### 2026-05-08 — Retention purge observability (PR [#298](https://github.com/lahavrud/rs-recruiting/pull/298), runbook in [#299](https://github.com/lahavrud/rs-recruiting/pull/299))
**Decision:** Emit `PurgedCandidatesCount` metric nightly (always — even count=0). Stale-purge alarm via missing data. New `ops-alerts` SNS topic for ops separately from billing. Per-candidate audit log line `retention.purge candidate_id=<id>` to `/rs-recruiting/worker` (later bumped to 400d retention).
**Why:** Compliance requires proving the purge ran; missing-data alarm catches dead worker / IAM regression.

### 2026-05-04 — Atomic deploy artifact (PR [#296](https://github.com/lahavrud/rs-recruiting/pull/296))
**Decision:** SHA-pinned ECR images for both api and frontend (`frontend/Dockerfile` multistage bakes `nginx.conf` + `dist/`). Per-SHA immutable S3 prefix `deploy/${SHA}/`. SSM `CURRENT_SHA` as version pointer. `scripts/rollback.sh` for one-shot SHA flip.
**Why:** 521 outage on 2026-05-04 was caused by stale-base push to `main` overwriting S3 deploy configs (last-writer-wins). Splitting the artifact across mutable S3 + ECR `:latest` allowed an old config + new image (or vice versa) to combine into untested state.

### 2026-05-04 — Nightly candidate retention purge (PR [#295](https://github.com/lahavrud/rs-recruiting/pull/295))
**Decision:** Arq cron at 03:00 UTC, eligibility = "every application is on a CLOSED job updated >365d ago AND not HIRED." Best-effort S3 resume delete + DB cascade. See [`RETENTION_PURGE.md`](./RETENTION_PURGE.md).
**Why:** Privacy policy commits to 12-month retention.

### Earlier infrastructure baseline (pre-2026-05)
- Cloudflare → single EC2 + managed RDS (cost-effective MVP shape)
- GitHub Actions OIDC role (no long-lived CI keys)
- SSM Parameter Store for secrets (TLS, DB URL, JWT, SMTP)
- DLM weekly EC2 snapshot, retain 4 (EBS PIT recovery)
- See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for higher-level decisions

---

## 5. Maintenance rules

1. **Any PR that touches AWS infra updates this file in the same PR.** Inventory tables stay accurate; decisions log gets a new entry.
2. **No standalone "diagram refresh" PRs.** Drift means the doc is wrong; if it can't be kept current, delete it.
3. **Don't rewrite the decisions log.** Supersede with a new entry that references the older one.

---

## 6. Related docs

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — high-level decisions (auth, framework, schema)
- [`RETENTION_PURGE.md`](./RETENTION_PURGE.md) — runbook for the nightly purge cron
- [`API_DESIGN.md`](./API_DESIGN.md), [`CONTEXT.md`](./CONTEXT.md), [`ROADMAP.md`](./ROADMAP.md) — product / domain context
- [Issue #303](https://github.com/lahavrud/rs-recruiting/issues/303) — pending: audit-log tamper evidence (Phase 1: INSERT-only grants)
