# Candidate Data Retention — Runbook

The 12-month candidate retention purge: what it does, how to verify it ran, how to investigate when it didn't, and how to extend it.

---

## What it is

A nightly background job that deletes candidate data past the 12-month retention window mandated by our privacy policy.

- **Schedule:** 03:00 UTC nightly (off-peak for our user base)
- **Runs in:** the `worker` ECS Fargate service
- **Defined in:** `src/core/tasks.py::purge_expired_candidate_data_task`
- **Eligibility logic:** `src/services/candidates_admin.py::purge_expired_candidates`

---

## Eligibility rule

A candidate is purged **only if every one of their applications** satisfies all three conditions:

1. Linked `Job.status == CLOSED`
2. `Job.updated_at < now - 365 days`
3. `Application.status != HIRED`

If even one application fails any condition, the candidate is preserved — companies may still need that data for payroll or dispute resolution. New candidates with zero applications are also preserved (no expiry has started).

The query is in `purge_expired_candidates`; it is the **single source of truth** for who gets deleted. Any change to retention policy goes there.

---

## What gets deleted, in order

For each eligible candidate:

1. The resume file in S3 — **permanently** (all object versions and delete markers are removed via `list_object_versions` + `delete_objects`; no version lingers after this call). Best-effort: failures are logged and ignored so a partial S3 outage cannot block compliance deletions.
2. All `Application` rows where `candidate_id` matches.
3. The `CandidateProfile` row itself.
4. An audit log line: `INFO retention.purge candidate_id=<id>`.

All DB writes happen inside one transaction (`transactional(session)`); a failure mid-batch rolls back cleanly.

---

## Observability

### Audit log

Every deletion emits one structured log line — ID only, no PII:

```
INFO  retention.purge candidate_id=42
```

This is the auditor evidence trail. Lives wherever the worker service's stdout goes (today: CloudWatch Logs, `/ecs/rs-recruiting-prod-worker`).

### CloudWatch metric

| Field | Value |
|---|---|
| Namespace | `RsRecruiting/Retention` |
| Metric | `PurgedCandidatesCount` |
| Unit | `Count` |
| Cadence | Once per cron run (nightly) |
| Production-only | Gated on `settings.environment == "production"` |
| On failure | Swallowed — DB delete is the source of truth |

The task **always emits a datapoint, even when count=0.** That is what makes the missing-data alarm meaningful.

### Alarm: `retention-purge-stale`

| Field | Value |
|---|---|
| Period | 86400s (24h) |
| Evaluation periods | 1 |
| Threshold | `Sum < 0` (effectively never breached by data — only by absence) |
| `treatMissingData` | `breaching` |
| Alarm + OK actions | `arn:aws:sns:us-east-1:<ACCOUNT_ID>:ops-alerts` |

The alarm fires when **no datapoint arrived in the last 26h**. Since the cron emits one datapoint nightly, missing data means the worker isn't running.

### Notification channel

SNS topic `ops-alerts`. Subscriptions: `<OPS_EMAIL>` (email).

To add another responder:

```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:<ACCOUNT_ID>:ops-alerts \
  --protocol email \
  --notification-endpoint <new-email>
```

The endpoint must confirm by clicking the AWS link before they start receiving notifications.

---

## Verifying it ran

```bash
# 1. Was a datapoint emitted in the last 24h?
aws cloudwatch get-metric-statistics \
  --namespace RsRecruiting/Retention \
  --metric-name PurgedCandidatesCount \
  --statistics Sum \
  --start-time $(date -u -d '1 day ago' +%FT%TZ) \
  --end-time   $(date -u +%FT%TZ) \
  --period 86400

# 2. Alarm state — should be OK after first run
aws cloudwatch describe-alarms --alarm-names retention-purge-stale \
  --query 'MetricAlarms[0].{State:StateValue,Reason:StateReason}'

# 3. What was deleted last night?
ssh ec2 'docker logs --since 24h rs-recruiting-worker-1 2>&1 | grep retention.purge'
```

---

## Investigating when it didn't run

Decision tree when the alarm fires:

```
retention-purge-stale fires
│
├── Worker service running? (ECS service running-task count ≥ 1)
│   ├── No  → check the ECS service events / stopped-task reason
│   └── Yes ↓
│
├── Worker logs show cron firing? (`docker logs worker | grep purge_expired`)
│   ├── No  → Arq cron config broken (check WorkerSettings.cron_jobs)
│   └── Yes ↓
│
├── Logs show metric emission failure? (`grep "Failed to emit"`)
│   ├── Yes → IAM regression on cloudwatch:PutMetricData (see IAM section below)
│   └── No  ↓
│
└── Settings.environment correctly set to "production"?
    ├── No  → env config drift (the metric is production-gated)
    └── Yes → unknown; escalate, run a manual purge to capture state
```

---

## IAM

The worker task role has `cloudwatch:PutMetricData` scoped to the `RsRecruiting/Retention` namespace via an IAM condition:

```json
{
  "Effect": "Allow",
  "Action": "cloudwatch:PutMetricData",
  "Resource": "*",
  "Condition": {
    "StringEquals": { "cloudwatch:namespace": "RsRecruiting/Retention" }
  }
}
```

`PutMetricData` does not support resource-level ARNs, so `Resource: "*"` is the only option — but the namespace condition keeps it least-privilege.

---

## Manual one-off purge

If you need to run the purge outside the cron schedule (e.g. compliance request to expedite a deletion):

```bash
ssh ec2
docker exec -it rs-recruiting-worker-1 python -c "
import asyncio
from src.core.infrastructure.database import async_session
from src.core.infrastructure.transactions import transactional
from src.services.candidates_admin import purge_expired_candidates

async def run():
    async with async_session() as s:
        async with transactional(s):
            n = await purge_expired_candidates(s)
    print(f'purged {n}')

asyncio.run(run())
"
```

The metric will not be emitted by a manual run — that's only the cron task wrapper. Add manual runs to the audit trail by capturing the `purged` count and the `retention.purge candidate_id=` log lines.

---

## What's intentionally not here

- **No dry-run mode.** Eligibility is a pure query; the audit log already proves what would have been deleted.
- **No batch limit.** The eligible set is small (it's the long tail of inactive candidates). If volume ever grows past tens of thousands per night, add `LIMIT` + repeat-until-empty.
- **No staging-only metric.** Outside production the task runs but skips the AWS call — no IAM noise, no CloudWatch pollution. If you want to test the metric path, set `environment=production` in a non-prod env and accept the namespace pollution.
- **No alarm for "the cron ran but deleted zero rows when it shouldn't have."** That's a correctness bug in `purge_expired_candidates`, not a runtime failure — covered by tests, not metrics.

---

## Related

- Service logic: `src/services/candidates_admin.py`
- Task wrapper: `src/core/tasks.py`
- Tests: `tests/core/test_tasks.py` (look for `purge_task_*`)
- Original implementation: PR #295
- Observability + alarm: PR #298
