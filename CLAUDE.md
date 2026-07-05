# RS Recruitment — Developer Guide

This file documents **invariants and non-obvious reasoning**, not inventory.
Directory listings and route tables go stale — discover those with `ls`/glob.
When you add something that carries a rule or a surprising constraint, add it
here; don't add entries whose purpose is obvious from the filename.

## Tooling

Prefer the `sigmap` MCP tools for architecture-level questions and cross-file
search. Its index (`.sigmap-cache.json`, gitignored) goes stale after refactors —
if results contradict the filesystem (wrong paths, missing packages), fall back
to direct reads and regenerate with `npx sigmap` (`npx sigmap --setup` installs
a git hook that keeps it fresh).

## Plan mode

Use plan mode before starting any change that touches `alembic/`, `libs/shared/rs_shared/services/auth/`, `.github/workflows/`, `libs/shared/rs_shared/models.py`, or `libs/shared/rs_shared/core/task_contract.py`. These areas have non-obvious invariants and hard-to-reverse consequences.

> **Backend layout (uv workspace).** The backend is split into three workspace
> members: `libs/shared` (`rs_shared` — the framework-free domain), `services/api`
> (`rs_api` — FastAPI routers + web infra), and `services/worker` (`rs_worker` —
> the SQS consumer). Import roots are `rs_shared` / `rs_api` / `rs_worker` (no more
> top-level `src.`). See `docs/service-data-ownership.md`.

## Path-scoped rules

Load the relevant rule file before planning changes in these areas:

- **Frontend** (design system, components, i18n, linting): `.claude/rules/frontend.md`  
  → any change touching `frontend/`
- **Auth** (JWT, sessions, activation flows, rate limiting): `.claude/rules/auth.md`  
  → any change touching `libs/shared/rs_shared/services/auth/` or `services/api/rs_api/api/auth/`
- **Migrations & data model** (alembic, SQLModel, N+1): `.claude/rules/migrations.md`  
  → any change touching `alembic/` or `libs/shared/rs_shared/models.py`
- **Task queue & worker** (wire contract, idempotency, boundaries): `.claude/rules/worker.md`  
  → any change touching `libs/shared/rs_shared/core/tasks.py`, `task_contract.py`, `matching.py`, or `services/worker/`
- **Tests** (conventions, fixtures, CI): `.claude/rules/tests.md`  
  → any change touching `tests/`
- **Infrastructure & CI/CD** (OIDC, SSM, CI workflows, deploy safety): `.claude/rules/infra.md`  
  → any change touching `.github/workflows/` or `scripts/`

## Tech Stack

- **Frontend**: React 19 + TypeScript + Vite + Tailwind v4
- **Backend**: FastAPI (Python) + SQLModel async + PostgreSQL
- **Auth**: JWT access token in `localStorage` + HttpOnly refresh-token cookie
- **i18n**: react-i18next, Hebrew-only, RTL forced globally via `<html dir="rtl" lang="he">`
- **Routing**: React Router v7

---

## Backend architecture

```
libs/shared/rs_shared/           # framework-free domain (installed into BOTH images)
├── models.py  enums.py  schemas/  templates/  assets/
├── services/                    # business logic — one package per actor:
│   │                            #   auth/ admin/ company/ candidate/ public/ utils/
│   │                            #   (underscore-prefixed modules are package-private helpers)
│   └── exceptions.py            # flat — imported by 15+ files
└── core/
    ├── tasks.py  task_contract.py  matching.py   # task queue (see rules/worker.md)
    ├── infrastructure/          # config, database, security, pagination, telemetry, …
    └── services/                # provider abstractions: email, storage, file
                                 # validation, embeddings, cv_extraction, generation

services/api/rs_api/             # FastAPI service (web stack: fastapi, uvicorn, slowapi)
├── main.py
├── infrastructure/              # web-only plumbing: auth deps, error→HTTP mapping,
│                                # slowapi limiter, request middleware
└── api/                         # routers mirror services/: auth/ admin/ company/
                                 #   candidate/ public/ seo/ + uploads, analytics,
                                 #   sentry_tunnel, _resume_streaming

services/worker/rs_worker/
└── worker.py                    # SQS consumer entry point (console script: rs-worker)
```

Non-obvious constraints in `core/`:

- `email_quota.py` tracks the daily send count and **warns** as free-tier limits
  approach — no hard enforcement; the provider's own 429 is the backstop.
- `file_validation.py` does magic-byte validation on uploads (blocks
  extension-spoofing, e.g. `malware.exe` renamed to `resume.pdf`). The FastAPI
  `UploadFile` wrapper over it is `rs_api/api/uploads.py`.
- `request_context.py` is framework-free on purpose — both services use it for
  log correlation.
- Storage and email are ABC + provider factories (`storage_local` for dev/test,
  `storage_s3` for prod) — code against the abstraction, never a provider.

### Task queue

Plain async functions registered in `TASK_REGISTRY` (`core/tasks.py`), dispatched
by the SQS worker. `enqueue_*` functions are the producer side: they push JSON to
SQS, or — when `SQS_QUEUE_URL` is unset (local dev) — run the task inline. The
wire format lives once in `core/task_contract.py` and is shared by producer and
consumer so they can't drift. The worker deletes a message on success and leaves
it for redelivery (eventually the DLQ) on failure; SQS is at-least-once, so tasks
must be idempotent. Full rules: `.claude/rules/worker.md`.

Current tasks: `send_email_task`, `build_data_export_task` (GDPR export ZIP),
`purge_expired_candidate_data_task` (nightly retention purge via EventBridge
Scheduler → SQS), and `embed_job_task` / `match_candidate_task`
(resume-matching embeddings, in `core/matching.py`).

---

## Frontend architecture

```
frontend/src/
├── components/       guards/ layout/ dashboard/ admin/ shared/ ui/
├── pages/            admin/ candidate/ company/ public/ + auth pages
│                     (per-page components co-located in pages/<section>/components/)
├── hooks/  services/  types/  utils/  contexts/  constants/
├── content/          articles (static content + registry)
├── locales/he/       one JSON per i18n namespace
├── styles/forms.ts   inputCls, textareaCls, selectCls
└── index.css         Tailwind @theme tokens + global utilities
```

Routes live in `App.tsx`. Guard mapping: `/admin/*` → `AdminRoute`,
`/company/*` → `CompanyRoute`, `/candidate/*` → `CandidateRoute`,
`/dashboard` → `ProtectedRoute` (role-aware); everything else is public.
Guards live in `components/guards/` — always import from there.

### AppShell routing logic

| Condition | Shell |
|---|---|
| `/`, auth pages (`/login`, `/register`, …), `/admin/applications/triage` | Bare |
| Authenticated (any role) | Header + Sidebar + `bg-page` |
| Unauthenticated (public) | `PublicHeader` + `bg-page` |

`/admin/applications/triage` is bare because it renders `fixed inset-0`; the
authenticated shell's `page-enter` `transform` would create a containing block
and clip the overlay.

`/jobs/*` always renders the public shell regardless of auth state.

### Non-obvious frontend invariants

- **Services** (`services/`): one file per backend domain, all built on the
  shared `axios` instance in `api.ts` (JWT bearer header + token storage via
  `@/utils/token`). Add new endpoints to the matching domain file, not a new
  ad-hoc client.
- **Types** (`types/`): mirror backend schemas, split by domain. `enums.ts`
  holds const-object mirrors of `rs_shared/enums.py` — plain objects, not TS
  `enum`, since `erasableSyntaxOnly` forbids enum runtime code.
- **Toast context split**: `ToastContext.tsx` owns state/timers and renders the
  provider; `toastContext.ts` holds the `createContext` call + types, so
  `useToast` can import the context without pulling in the provider component
  (keeps `react-refresh/only-export-components` happy).
- **AuthContext**: resolves initial state synchronously from `localStorage`,
  then verifies via `/api/auth/me` — see `.claude/rules/auth.md`.
- **`lazyWithRetry`**: drop-in `React.lazy` replacement that recovers from
  stale-chunk errors after a deploy invalidates hashed chunk filenames — use it
  for all route-level lazy imports.
- **`useInfiniteList`** pairs with the backend's `CursorPage[T]` keyset-pagination
  envelope — use both ends together for any new infinite list.
- **`passwordComplexity.ts`** is a client-side mirror of the backend rule and
  returns an i18n key for the first failing rule — change both sides together.
- **`ResumeButton`** (from `ResumeViewer`): portals to `document.body`; iOS uses
  `navigator.share()` because Safari ignores `download` on blob URLs. Never
  build a custom resume-viewing flow.

---

## Running Locally

`uv sync` provisions the whole workspace (the root depends on the api + worker
members, so all three packages install editable).

```bash
# Backend inner loop (fast): backing services in containers + uvicorn on the host.
make services            # db + mailpit + localstack (bare `docker compose up -d`)
uv sync && uv run uvicorn rs_api.main:app --reload   # tasks run inline (SQS unset)

# Full containerized split: adds the api + worker images (compose `app` profile).
# `make` builds the shared base then both service images (requires docker buildx):
make up                  # = make images && docker compose --profile app up -d
make logs                # tail api + worker
make down                # stops everything

cd frontend && npm run dev                         # frontend (Vite, :3000)
```

The api + worker carry compose `profiles: ["app"]`, so a bare `docker compose up`
starts only the backing services. Use `make up` for the full stack, `make services`
(or plain `uvicorn`) for day-to-day backend work.

Adding deps: `uv add <pkg> --package rs-recruiting-{shared,api,worker}` (pick the
narrowest member — keep the web stack out of `shared`/`worker`). No
`requirements.txt`. Always commit `uv.lock` after touching any `pyproject.toml`.

Per-member dependency boundaries are enforced by import-linter (contracts in the
root `pyproject.toml`, run locally via `uv run lint-imports` / `make check`; CI
enforces them via `scripts/validate_imports.py` and
`tests/test_domain_is_framework_free.py`).

---

## GitHub Conventions — MUST follow

### Branches
`<type>/<short-kebab-summary>` — types: `feat`, `fix`, `chore`, `docs`, `hotfix`, `feature`, `refactor`. Match existing types.

### Commits
Conventional Commits: `feat(auth): ...`, `fix(email): ...`, `chore: ...`

### Pull requests
Title = Conventional Commit style. Body **must** follow `.github/pull_request_template.md` (Summary / Why / Changes / How to Test / Related Issue). Write `N/A` if no issue. No extra sections.

### Issues
Use matching template from `.github/ISSUE_TEMPLATE/` (`bug_report.md`, `feature_request.md`, `task.md`). Fill every section including Milestone.

---

## Validation — MUST run before every commit

```bash
uv run ruff check . && uv run ruff format --check .   # backend lint
cd frontend && npx tsc --noEmit && npm run lint        # frontend lint
```

Before opening a PR, run the full CI-parity gate (adds import-linter, the
validator scripts, and both test suites):

```bash
make check
```
