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
backend/src/
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
├── utils/            formatDate.ts, validators.ts, apiError, analytics, focusFirstError
├── contexts/         AuthContext
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
| `/jobs` `/jobs/:id` `/jobs/:id/apply` | — | Public job board + apply |
| `/dashboard` | `ProtectedRoute` | Role-aware `DashboardPage` |
| `/admin/companies` `/admin/jobs` `/admin/applications` `/admin/candidates` | `AdminRoute` | Admin pages |
| `/admin/applications/triage` | `AdminRoute` | `AdminApplicationsTriagePage` |
| `/company/jobs` | `CompanyRoute` | `CompanyJobsPage` |
| `/candidate/profile` | `CandidateRoute` | `CandidateProfilePage` |
| `/candidate/applications` `/candidate/applications/:id` | `CandidateRoute` | Candidate app pages |

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

### Project board — MUST keep in sync
All tracked work across **every** rs-recruiting repo flows through the shared GitHub Project **"RS Recruiting"** (owner `lahavrud`, project `#1`). Automation handles two transitions: new issues/PRs are **auto-added** to the board, and items move to **Done ✅** when their issue/PR is closed or merged. You drive the rest:

- Every non-trivial task has an issue on the board. When you **start** work, set Status → **In Progress 🏗️**.
- When you open the PR, set Status → **In Review 🔍**, and **always** link the issue with `Closes #N` so the merge auto-moves it to Done. Never manually set Done — let the close/merge do it.
- If blocked on an external dependency, set Status → **Blocked ⛔**.

Set status from the CLI (resolve the item id with `gh project item-list 1 --owner lahavrud`):
```bash
gh project item-edit --project-id PVT_kwHODX-d9M4BMa98 --id <ITEM_ID> \
  --field-id PVTSSF_lAHODX-d9M4BMa98zg7tTnw \
  --single-select-option-id <STATUS>   # In Progress 🏗️ 47fc9ee4 · In Review 🔍 02e018f5 · Done ✅ 98236657 · Blocked ⛔ f75ad846 · Backlog c96e866b
```

---

## Linting — MUST run before every commit

```bash
uv run ruff check . && uv run ruff format --check .   # backend
cd frontend && npx tsc --noEmit && npm run lint        # frontend
```
