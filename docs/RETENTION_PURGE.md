# Nightly Data-Hygiene — Runbook

The nightly cleanup task runs seven independent data-hygiene jobs, including the 12-month candidate retention purge required by our privacy policy. Each sub-task is separately transacted; a failure in one does not abort the others.

---

## Schedule & location

- **Schedule:** 03:00 UTC nightly (EventBridge Scheduler → SQS → worker)
- **Runs in:** the `rs_worker` container on the EC2 host
- **Dispatcher:** `rs_shared.core.tasks::nightly_cleanup_task`
- **Wire-format task key:** `purge_expired_candidates` (backward-compat with existing EventBridge rule)

---

## Sub-tasks

### 1. `purge_expired_candidates` (12-month retention purge)

**Eligibility** — a candidate is purged only when *every* one of their applications satisfies all three conditions:

1. Linked `Job.status == CLOSED`
2. `Job.updated_at < now − 365 days`
3. `Application.status != HIRED`

Candidates with any active application, recently-closed job, or HIRED status are preserved. New candidates with zero applications are also preserved (no expiry clock has started).

For each eligible candidate:
1. Resume file in S3 deleted (best-effort; failures are logged, deletion continues).
2. All `Application` rows deleted.
3. `CandidateProfile` row deleted.
4. Audit log entry: `INFO retention.purge candidate_id=<id>` (ID only, no PII).

**Service:** `rs_shared.services.admin._candidates_purge::purge_expired_candidates`

---

### 2. `purge_unactivated_candidate_users` (7-day stale-registration sweep)

Deletes CANDIDATE `User` rows that were registered but never activated within the 7-day window.

**Eligibility:**
- `User.role == CANDIDATE`
- `User.is_active == False`
- `User.created_at < now − 7 days`
- No valid (unused + unexpired) `ActivationToken` still pending

The `User` hard-delete cascades to `RefreshToken`, `PasswordResetToken`, `ActivationToken`, `DataExportRequest`, `AccountDeletionToken`. The FK on `CandidateProfile.user_id` is SET NULL, preserving the profile as an anonymous lead.

---

### 3. `purge_expired_data_export_zips` (GDPR export cleanup)

Deletes `DataExportRequest` rows and their S3 ZIP files.

**Eligibility:**
- `expires_at < now` (24h TTL elapsed), OR
- `used = true AND created_at < now − 24h` (downloaded + grace period elapsed)

Storage deletion is best-effort: if the file cannot be deleted the row is **preserved** (not deleted) to avoid orphaning data. A warning is logged.

---

### 4. `purge_expired_account_deletion_tokens`

Deletes stale `AccountDeletionToken` rows.

**Eligibility:**
- `expires_at < now`, OR
- `used = true`

---

### 5. `purge_expired_activation_tokens` (30-day traceability window)

Deletes `ActivationToken` rows past the 30-day traceability window. Tokens are retained for 30 days after `expires_at` so that stale-link activation attempts can still be attributed.

**Eligibility:** `expires_at < now − 30 days`

---

### 6. `redact_expired_email_outbox` (30-day email content window)

`email_outbox` rows hold the fully rendered email: subject (which can name the job), body, HTML, and base64 attachments such as contract PDFs. The table has no link back to the candidate, so the 12-month purge cannot follow it; it is bounded by age instead.

Clears `subject`, `body`, `html_body`, `attachments` and `last_error`, keeping only the delivery record (`to_addrs`, status, timestamps, `provider_message_id`) so "did they get it, and when?" stays answerable.

**Eligibility:**
- `status IN (SENT, FAILED)`: in-flight rows (`PENDING` / `SENDING`) belong to the worker and the sweeper and are never touched
- `created_at < now − EMAIL_OUTBOX_REDACT_AFTER_DAYS` (default 30)
- not already redacted (`body != ''`)

`updated_at` is not bumped: it is the sweeper's "time in this state" clock.

---

### 7. `purge_expired_email_outbox` (90-day email record window)

Deletes terminal outbox rows outright.

**Eligibility:**
- `status IN (SENT, FAILED)`
- `created_at < now − EMAIL_OUTBOX_DELETE_AFTER_DAYS` (default 90)

Keep the delete window shorter than the 365-day candidate retention: an email sent to a candidate is gone well before their record could be purged, and a candidate who deletes their account has their emails stripped of content within 30 days and removed entirely within 90.

---

## Observability

### Structured log lines (no PII)

```
INFO  retention.purge candidate_id=42
INFO  cleanup.unactivated_user user_id=17
INFO  nightly_cleanup_complete purge_expired_candidates=3 purge_unactivated_users=1 ...
```

### OTel metrics (→ Alloy → Mimir)

| Metric name | Sub-task |
|---|---|
| `purged_candidates` | 12-month retention purge |
| `purged_unactivated_users` | Stale-registration sweep |
| `purged_export_zips` | GDPR export cleanup |
| `purged_deletion_tokens` | Deletion token sweep |
| `purged_activation_tokens` | Activation token sweep |
| `redacted_email_outbox` | Email outbox content redaction |
| `purged_email_outbox` | Email outbox row deletion |
| `last_purge_ran_at` | Unix timestamp of last successful run |

All metrics carry an `environment` attribute. Query in Grafana Mimir.

---

## Verifying it ran

```bash
# 1. Last cleanup timestamp (Grafana Mimir)
#    Query: last_purge_ran_at{environment="production"}

# 2. Worker logs for the summary line
docker logs --since 24h rs-recruiting-worker-1 2>&1 | grep nightly_cleanup_complete

# 3. Retention audit trail
docker logs --since 24h rs-recruiting-worker-1 2>&1 | grep "retention.purge"
```

---

## Manual one-off purge

If you need to run the retention sub-task outside the cron schedule:

```bash
docker exec -it rs-recruiting-worker-1 python -c "
import asyncio
from rs_shared.core.infrastructure.database import async_session
from rs_shared.core.infrastructure.transactions import transactional
from rs_shared.services.admin._candidates_purge import purge_expired_candidates

async def run():
    async with async_session() as s:
        async with transactional(s):
            n = await purge_expired_candidates(s)
    print(f'purged {n}')

asyncio.run(run())
"
```

---

## Related

- Dispatcher: `libs/shared/rs_shared/core/tasks.py::nightly_cleanup_task`
- Sub-task helpers: `libs/shared/rs_shared/services/admin/maintenance.py`
- Outbox windows: `email_outbox_redact_after_days` / `email_outbox_delete_after_days` in `libs/shared/rs_shared/core/infrastructure/config.py`
- Retention logic: `libs/shared/rs_shared/services/admin/_candidates_purge.py`
- Tests: `tests/services/admin/test_maintenance.py`, `tests/core/test_tasks.py`
