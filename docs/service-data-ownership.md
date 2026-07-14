# Service data ownership

The backend is split into independently deployable services (see the uv
workspace under `libs/` and `services/`):

- **api** (`rs_api`) — the FastAPI HTTP service.
- **worker** (`rs_worker`) — the SQS task consumer.
- **shared** (`rs_shared`) — the domain library both depend on (models, schemas,
  service logic, infrastructure). Not a runtime service.

## One database, for now

All services share a **single PostgreSQL** instance (pgvector for the
resume-matching embedding columns). There is no database-per-service split yet.
This document records *logical* ownership so a future physical split has a
starting map; today it is a convention, not an enforced boundary.

The schema is owned by the **api** service: migrations live in `alembic/`, the
api image carries them, and the api applies `alembic upgrade head` (prod deploy,
and the local `docker compose` api command). The worker never runs migrations.

## Table ownership

"Owner" = the service responsible for the table's lifecycle and the primary
writer. "Other writers" notes cross-service writes that exist today.

| Table | Owner | Other writers | Notes |
|---|---|---|---|
| `user` | api | — | Auth identities. |
| `companyprofile` | api | — | Company accounts + approval state. |
| `candidateprofile` | api | **worker** | Worker writes `parsed_text`, `embedding`, `resume_summary` during matching; api owns the rest. Worker also purges expired rows (retention). |
| `job` | api | **worker** | Worker writes `embedding` on (re)publish. |
| `application` | api | — | Job applications. |
| `matchsuggestion` | api | — | Match results surfaced to admins (live cosine query at read time). |
| `invitetoken` | api | — | Gated company-registration invites. |
| `activationtoken` | api | — | Company/candidate activation. |
| `passwordresettoken` | api | — | Password reset. |
| `refreshtoken` / `usedrefreshtoken` | api | — | Refresh-token rotation + replay guard. |
| `audit_log` | api | — | Admin/audit events. |
| `data_export_request` | api | **worker** | api creates the pending request; the worker's `build_data_export` task fills + finalises it. |
| `email_quota` | **worker** | — | Daily send counter; the worker bumps it after each send (`increment_and_alert`, a raw-SQL upsert). Modeled as `EmailQuota` in `models.py` (so `create_all` builds it) and created by migration `e03b8aa073a3` in prod. |

## Cross-service contract

The api (producer) and worker (consumer) communicate **only** over SQS, never by
calling each other's code. The message wire format is defined once in
`rs_shared/core/task_contract.py` (`TaskName` + `build_*_message` /
`decode_message`) and shared by both, so the two sides cannot drift. Tasks:
`send_email`, `build_data_export`, `purge_expired_candidates`, `embed_job`,
`match_candidate`.

## Service-domain independence (within the api)

The five actor domains under `rs_shared/services/` (`auth`, `admin`, `company`,
`candidate`, `public`) are **modules of the modular monolith: none imports
another**. This is enforced by an `independence` import-linter contract (root
`pyproject.toml`). Shared logic lives in the kernel (`services/utils`), or — when
a domain genuinely needs another's behavior — is inverted behind a `Protocol`
injected at the composition root (`rs_api`). The public apply flow's candidate
account creation uses this pattern: `services/utils/candidate_provisioning.py`
defines the `CandidateProvisioner` boundary; `rs_api` injects auth's
`register_candidate`, so `public` never imports `auth`. A companion `forbidden`
contract keeps the kernel from importing back into any domain.

## When splitting the database later

- `email_quota` is already worker-owned and self-contained — the cleanest first
  candidate to move to a worker-local store.
- The worker's writes to `candidateprofile` / `job` are narrow column updates
  (embeddings, parsed text, summary); these would become api-mediated writes or
  a dedicated matching store if those tables move api-side.
- `data_export_request` is co-written; a split would make the worker write via an
  api endpoint or its own table.
