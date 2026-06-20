# RS Recruitment — Developer Guide

## Tooling

Use `sigmap` MCP tools to navigate and search the codebase instead of reading files directly.

## Plan mode

Use plan mode before starting any change that touches `alembic/`, `src/services/auth/`, `.github/workflows/`, or `src/models.py`. These areas have non-obvious invariants and hard-to-reverse consequences.

## Path-scoped rules

Load the relevant rule file before planning changes in these areas:

- **Frontend** (design system, components, i18n, linting): `.claude/rules/frontend.md`  
  → any change touching `frontend/`
- **Auth** (JWT, activation flows, rate limiting): `.claude/rules/auth.md`  
  → any change touching `src/services/auth/` or `src/api/auth/`
- **Migrations & data model** (alembic, SQLModel, N+1): `.claude/rules/migrations.md`  
  → any change touching `alembic/` or `src/models.py`
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

## Frontend Architecture

### Directory layout

```
src/
├── api/
│   ├── auth/         login.py, registration.py, candidate_registration.py, activation.py,
│   │                 password_reset.py, password_change.py, invites.py
│   ├── admin/        companies.py, invites.py, jobs.py, applications.py, candidates.py, audit.py
│   ├── company/      jobs.py, profile.py, resumes.py
│   ├── public/       jobs.py (board), applications.py (apply flow)
│   ├── seo/          (prerender package)
│   └── sentry_tunnel.py
├── services/
│   ├── auth/         session.py, registration.py, activation.py, password_reset.py
│   ├── admin/        companies.py, company_approval.py, company_profiles.py, invites.py,
│   │                 jobs.py (CRUD), jobs_workflow.py (approve/reject/contact),
│   │                 applications.py, candidates.py
│   ├── company/      jobs.py, profile.py, candidates.py
│   ├── public/       jobs.py, applications.py
│   ├── utils/        audit.py, contract_pdf.py, legal.py
│   └── exceptions.py (flat — imported by 15+ files)
├── core/             tasks.py, worker.py, infrastructure/, services/ — see "Backend core systems" below
└── worker.py         SQS worker entry point — see "Backend core systems" below

frontend/src/
├── components/
│   ├── guards/       AdminRoute, CompanyRoute, CandidateRoute, ProtectedRoute
│   ├── layout/       AppShell, Header, Sidebar
│   ├── dashboard/    CandidateDashboard and sub-components, dashboardUtils.ts
│   ├── admin/        ActiveFilterChip, AnimatedAccordion, SearchableMultiSelect, SearchableSelect, …
│   └── ui/           Button, Eyebrow, Field, PageHeader, ResumeViewer, StatusBadge, CompanyName, …
├── pages/
│   ├── admin/        AdminApplicationsPage, AdminApplicationsTriagePage, + components/
│   ├── public/       JobBoardPage, JobDetailPage, ApplicationPage, LandingPage + components/
│   ├── candidate/    CandidateApplicationsPage, CandidateProfilePage + components/
│   └── …             Auth pages, company pages, DashboardPage
├── utils/            formatDate.ts, validators.ts, apiError, analytics, focusFirstError,
│                     token.ts, consent.ts, mime.ts, passwordComplexity.ts, resume.ts,
│                     lazyWithRetry.ts, isDirty.ts — see "Frontend systems" below
├── hooks/            useInfiniteList, useConfirmableClose, useAutoOpenFromRouteState,
│                     useDebounce, usePageTitle, useResetOnTrigger, useImageLoaded, useToast
├── services/         api.ts, auth.ts, jobs.ts, candidate.ts, companyJobs.ts,
│                     adminApplications.ts, adminCandidates.ts, adminCompanies.ts,
│                     adminInvites.ts, adminJobs.ts, admin.ts (deprecated barrel)
├── types/            api.ts (barrel), auth.ts, candidates.ts, companies.ts, enums.ts,
│                     health.ts, invites.ts, jobs.ts
├── contexts/         AuthContext, ToastContext (provider) + toast-context (context/types)
├── styles/           forms.ts (inputCls, textareaCls, selectCls)
├── locales/he/       common, auth, admin, publicJobs, candidate, company, dashboard,
│                     landing, about, nav, cookies, resume, ui
└── index.css         Tailwind @theme tokens + global utilities
```

### AppShell routing logic

| Condition | Shell |
|---|---|
| `/`, `/login`, `/register`, `/register-candidate`, `/activate`, `/admin/applications/triage` | Bare |
| Authenticated (any role) | Header + Sidebar + `bg-page` |
| Unauthenticated (public) | `PublicHeader` + `bg-page` |

`/admin/applications/triage` is bare because it renders `fixed inset-0`; the authenticated shell's `page-enter` `transform` would create a containing block and clip the overlay.

`/jobs/*` always renders the public shell regardless of auth state.

### Routes (App.tsx)

| Path | Guard | Page |
|---|---|---|
| `/` | — | `LandingPage` |
| `/login` `/register` `/register-candidate` `/activate` | — | Auth pages |
| `/about` | — | `AboutPage` |
| `/contact` | — | `ContactPage` |
| `/articles` | — | `ArticlesIndexPage` |
| `/articles/:slug` | — | `ArticlePage` |
| `/jobs` `/jobs/:id` `/jobs/:id/apply` | — | Public job board + apply |
| `/dashboard` | `ProtectedRoute` | Role-aware `DashboardPage` |
| `/admin/companies` `/admin/jobs` `/admin/applications` `/admin/candidates` | `AdminRoute` | Admin pages |
| `/admin/applications/triage` | `AdminRoute` | `AdminApplicationsTriagePage` |
| `/company/jobs` | `CompanyRoute` | `CompanyJobsPage` |
| `/candidate/profile` | `CandidateRoute` | `CandidateProfilePage` |
| `/candidate/applications` | `CandidateRoute` | `CandidateApplicationsPage` |
| `/candidate/applications/:id` | `CandidateRoute` | `CandidateApplicationDetailPage` |

---

## Backend core systems

### `src/core/tasks.py` + `src/worker.py` — async task queue

Plain async functions (no Arq-style context arg) registered in `TASK_REGISTRY` and dispatched by the SQS worker. `enqueue_*` functions in `tasks.py` are the producer side: they push a JSON message to SQS, or — when `SQS_QUEUE_URL` is unset (local dev) — run the task inline/in-process instead. Tasks:

- `send_email_task` — sends via the configured email provider, then bumps the daily quota counter
- `build_data_export_task` — builds a candidate's GDPR data export ZIP and emails the download link (idempotent — a pending export makes it a no-op, since SQS is at-least-once)
- `purge_expired_candidate_data_task` — nightly retention purge of candidates past the 12-month window (triggered by EventBridge Scheduler → SQS)

`src/worker.py` is the queue consumer entry point (`python -m src.worker`): long-polls SQS, dispatches each message's `task` field through `TASK_REGISTRY`, deletes the message on success, and leaves it for SQS redelivery (eventually the DLQ) on failure. Handles `SIGTERM` gracefully — finishes the in-flight batch before exiting.

### `src/core/infrastructure/` — cross-cutting backend plumbing

| File | Purpose |
|---|---|
| `config.py` | App settings (env-driven, pydantic) |
| `database.py` | Async engine/session setup |
| `database_helpers.py` | Query helpers to cut boilerplate in service functions |
| `dependencies.py` | FastAPI auth/authorization dependencies |
| `error_handling.py` | Maps service exceptions → HTTP exceptions via opaque error codes (never leaks raw exception text/PII to clients) |
| `invite_tokens.py` | DB-backed invite tokens for gated company registration |
| `limiter.py` | slowapi rate-limiter configuration |
| `middleware.py` | Request correlation IDs + APM latency logging |
| `pagination.py` | Cursor-based keyset pagination for admin list endpoints |
| `security.py` | Password hashing + JWT helpers |
| `telemetry.py` | OpenTelemetry SDK init (traces/metrics/logs), shared by `main.py` and `worker.py` |
| `transactions.py` | Async transaction context manager for write endpoints |

### `src/core/services/` — provider abstractions

| File | Purpose |
|---|---|
| `email.py` | Email provider abstraction (ABC + concrete providers) |
| `email_quota.py` | Tracks daily send count, warns as free-tier limits approach (no hard enforcement — provider's own 429 is the backstop) |
| `file_validation.py` | Magic-byte validation on uploads (blocks extension-spoofing, e.g. `malware.exe` renamed to `resume.pdf`) |
| `storage.py` | Storage abstraction layer (ABC + provider factory) |
| `storage_local.py` | Local filesystem storage provider (dev/test) |
| `storage_s3.py` | AWS S3 storage provider |

---

## Frontend systems

### Contexts (`frontend/src/contexts/`)
- `AuthContext.tsx` — session state (see `.claude/rules/auth.md` for the sync-then-verify invariant)
- `ToastContext.tsx` — `ToastProvider`, owns toast state/timers and renders the provider
- `toast-context.ts` — the `createContext` call + `Toast`/`ToastContextValue` types, split out so `useToast` can import the context without pulling in the provider component (keeps `react-refresh/only-export-components` happy)

### Hooks (`frontend/src/hooks/`)
| Hook | Purpose |
|---|---|
| `useInfiniteList` | Cursor-based infinite-scroll list state, paired with the backend's `CursorPage[T]` envelope |
| `useConfirmableClose` | "Discard unsaved changes?" confirm-dialog wrapper for closing dirty forms |
| `useAutoOpenFromRouteState` | Reads a value off router navigation state, opens a panel with it, then clears the state so back-navigation doesn't reopen it |
| `useDebounce` | Returns a debounced copy of a value (e.g. search inputs) |
| `usePageTitle` | Sets `document.title` and focuses the page's `[data-page-heading]` element on mount |
| `useResetOnTrigger` | Runs a reset callback whenever a trigger value becomes truthy (dialog-open / entity-arrived patterns) |
| `useImageLoaded` | Tracks whether an image `src` has finished loading (for CSS background-image elements with no native load event) |
| `useToast` | Accessor for `ToastContext` — throws if used outside `ToastProvider` |

### Services (`frontend/src/services/`)
API client layer, one file per backend domain, all built on a shared `axios` instance (`api.ts`, handles the JWT bearer header and token storage via `@/utils/token`): `auth.ts`, `jobs.ts`, `candidate.ts`, `companyJobs.ts`, and the admin-scoped `adminApplications.ts` / `adminCandidates.ts` / `adminCompanies.ts` / `adminInvites.ts` / `adminJobs.ts`. `admin.ts` is a deprecated barrel re-export kept only for external consumers not yet migrated to the domain-scoped files.

### Types (`frontend/src/types/`)
TypeScript type definitions mirroring backend schemas, split by domain: `auth.ts`, `candidates.ts`, `companies.ts`, `enums.ts` (const-object mirrors of `src/enums.py` — plain objects, not TS `enum`, since `erasableSyntaxOnly` forbids enum runtime code), `health.ts`, `invites.ts`, `jobs.ts`. `api.ts` is a barrel re-exporting all of the above for backward compatibility with existing `from "@/types/api"` imports.

### Utils (`frontend/src/utils/`) — additions
- `token.ts` — `localStorage` access-token get/set/remove
- `consent.ts` — cookie-consent choice persistence (`cookie_consent` key)
- `mime.ts` — MIME-type ↔ file-extension mapping for resume uploads
- `passwordComplexity.ts` — client-side mirror of the backend's password complexity rule, returns an i18n key for the first failing rule
- `resume.ts` — resume upload constants (allowed extensions, max size) + filename helpers
- `lazyWithRetry.ts` — drop-in `React.lazy` replacement that recovers from stale-chunk errors after a deploy invalidates hashed chunk filenames
- `isDirty.ts` — shallow dirty-check via `JSON.stringify` comparison, drives discard-changes confirms

---

## Running Locally

```bash
uv sync && uv run uvicorn src.main:app --reload   # backend
cd frontend && npm run dev                         # frontend
```

No `requirements.txt` — use `uv add <pkg>`. Always commit `uv.lock` after touching `pyproject.toml`.

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

## Linting — MUST run before every commit

```bash
uv run ruff check . && uv run ruff format --check .   # backend
cd frontend && npx tsc --noEmit && npm run lint        # frontend
```
