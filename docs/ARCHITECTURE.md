# Architecture Decisions

This document captures all architectural decisions made for the RS Recruitment MVP, with references to GitHub Issues where decisions were discussed and implemented.

---

## Table of Contents

1. [Design Principles](#design-principles)
2. [Authentication Model](#authentication-model)
3. [Infrastructure Decisions](#infrastructure-decisions)
4. [Frontend Architecture](#frontend-architecture)
5. [Backend Architecture](#backend-architecture)
6. [Database Schema](#database-schema)
7. [Deployment & DevOps](#deployment--devops)
8. [Code Quality & Standards](#code-quality--standards)

---

## Design Principles

These principles guide all architectural decisions:

- **Monolith First** – Single deployable service with clear domain boundaries
- **Vertical Slices** – Features are developed end-to-end (DB → Business Logic → API → Tests)
- **Admin as Gatekeeper** – All public data requires admin approval
- **Match is the Product** – The Application entity is the system core
- **Low friction MVP** – Minimal auth surface, minimal public access
- **Future-ready** – Decisions documented, refactors anticipated
- **Architecture-First** – Critical infrastructure decisions made before dependent features

**Related Issues:**
- [#15](https://github.com/lahavrud/rs-recruiting/issues/15) - docs: setup project architecture, roadmap, and ai context

---

## Authentication Model

### Three-Role Auth Model

**Decision:** All three user types authenticate with JWT — Admins, Companies, and Candidates each have their own registration/activation paths but share a single `User` table with a `role` discriminator.

**Implementation:**
- **Admins** (`role: ADMIN`) — seeded directly, no public registration
- **Companies** (`role: COMPANY`) — self-register at `/register`; admin approves → activation email → `/activate?token=` (48h TTL)
- **Candidates** (`role: CANDIDATE`) — self-register at `/register-candidate`; activation email (2h TTL) → `/activate?token=` → `CandidateProfile` created; consent IP/UA captured from the activation request

**Auth mechanics:**
- JWT access token in `localStorage`; HttpOnly refresh-token cookie set by backend
- `AuthContext` resolves initial state synchronously from `localStorage`, then verifies via `/api/auth/me` on mount
- Account lockout after repeated failed logins (`failed_login_attempts` + `locked_until` on `User`)
- Password reset: `POST /api/auth/forgot-password` → email link → `POST /api/auth/reset-password`

**Related Issues:**
- [#25](https://github.com/lahavrud/rs-recruiting/issues/25) - feat: minimal auth system (registration + login)
- [#23](https://github.com/lahavrud/rs-recruiting/issues/23) - feat: company onboarding (auth + db)
- [#604](https://github.com/lahavrud/rs-recruiting/issues/604) - feat(candidate): candidate registration + activation (Sprint 11)

**Status:** ✅ Implemented

---

## Infrastructure Decisions

### 1. File Storage Strategy

**Problem:** `CandidateProfile.resume_path` implies file storage, but Docker containers are ephemeral. Local file storage will be lost on container restart/redeploy.

**Decision:** Implement a storage abstraction layer supporting multiple providers (Local, S3, MinIO) to enable resume uploads without vendor lock-in.

**Options Considered:**
- **AWS S3** – Production-ready, scalable, pay-per-use
- **Cloudinary** – Image/document optimization built-in
- **MinIO** – Self-hosted S3-compatible, good for dev/staging
- **Local Volume Mount** – Only for development, not production

**Chosen Solution:** Storage abstraction layer with provider abstraction interface
- **Local Storage** – For development and tests (`src/core/services/storage.py::LocalStorageProvider`)
- **S3/MinIO Storage** – For production (`src/core/services/storage.py::S3StorageProvider`)
- Provider selection via `STORAGE_PROVIDER` environment variable (`local` or `s3`)

**Implementation:**
- Abstract base class: `StorageProvider` in `src/core/services/storage.py`
- Methods: `upload_file()`, `get_file_url()`, `delete_file()`
- File validation: Size limits and file type checking
- Configuration: `src/core/infrastructure/config.py` with `storage_provider`, `aws_s3_bucket_name`, `local_storage_path`

**Related Issues:**
- [#43](https://github.com/lahavrud/rs-recruiting/issues/43) - feat(infra): Implement storage abstraction layer for file uploads (S3/MinIO/Local) ✅ CLOSED
- [#30](https://github.com/lahavrud/rs-recruiting/issues/30) - infra: integrate AWS S3 and SES services ✅ CLOSED

**Status:** ✅ Implemented

---

### 2. Email/Notification Service

**Problem:** Notifications are scheduled late (Phase 4), but admins need real-time alerts when candidates apply. Without email service, admins must manually refresh dashboard.

**Decision:** Integrate email service early (Infrastructure phase) with async task processing for guaranteed delivery.

**Options Considered:**
- **SMTP (Gmail/SendGrid)** – Simple, reliable, works with any provider
- **SendGrid API** – Transactional email service, better deliverability
- **AWS SES** – Cost-effective at scale
- **Postmark** – Developer-friendly, great deliverability

**Chosen Solution:** Email abstraction layer with SQS-based async task queue
- **Development:** SMTP to Mailpit (`docker-compose` service on port 1025; web UI at http://localhost:8025) — no provider account needed
- **Production:** Resend via SMTP relay (`EMAIL_PROVIDER=smtp`; `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` loaded from SSM). AWS SES was considered but sandbox migration to production was blocked.
- **Code abstractions:** `SESEmailProvider` and `SMTPEmailProvider` in `src/core/services/email.py`; selection via `EMAIL_PROVIDER` env var
- **Task Queue:** AWS SQS → `src/worker.py` worker process (`src/core/tasks.py`)
- **Retry Logic:** SQS at-least-once delivery; tasks are idempotent; DLQ captures failures
- Local dev: tasks run inline when `SQS_QUEUE_URL` is not set (no queue needed)

**Implementation:**
- Abstract base class: `EmailProvider` in `src/core/services/email.py`
- Implementations: `SESEmailProvider`, `SMTPEmailProvider`
- Task producer: `enqueue_email_task()` in `src/core/tasks.py` — call sites unchanged from Arq era
- Worker: `src/worker.py` — polls SQS, dispatches to `TASK_REGISTRY`
- Configuration: `src/core/infrastructure/config.py`

**Notification Triggers (all implemented):**
- Candidate applies → email admin + confirmation email to candidate
- Company self-registers → email admin (approval needed)
- Job posted by company → email admin (approval needed)
- Job approved by admin → email company
- Job rejected by admin → email company
- Admin contacts company about a job → email company
- Company approved by admin → email company (activation link)
- Admin invite sent → email invite with registration URL
- Candidate registers → activation email (2h TTL)
- Password reset requested → reset-link email
- GDPR data export ready → download-link email to candidate

**Related Issues:**
- [#44](https://github.com/lahavrud/rs-recruiting/issues/44) - feat(infra): Implement async task processing ✅ CLOSED
- [#30](https://github.com/lahavrud/rs-recruiting/issues/30) - infra: integrate AWS S3 and SES services ✅ CLOSED

**Status:** ✅ Fully implemented

---

### 2a. Email Quota Throttling

**Problem:** Resend's free tier allows 100 emails/day and 3,000/month. Introducing bulk notifications (e.g. closing a job notifies every applicant) could exhaust the daily quota in a single worker flush, silently stopping transactional emails (password reset, activation) for the rest of the day.

**Decision:** Add two independent safeguards at the worker level — a send-rate throttle and a DB-backed quota counter with log alerts.

**Options Considered:**
- **Hard stop at limit** — reject sends once quota is hit. Rejected: transactional emails (password reset, activation) cannot be dropped silently; DLQ retry-next-day is not built into SQS without custom delay logic.
- **Redis token bucket** — distributed, precise per-second throttle. Rejected: no Redis in the stack; single-worker deployment doesn't need distributed coordination.
- **Reactive 429 handling only** — catch Resend's 429 and back off. Rejected: gives no advance warning and risks dropping urgent transactional mail.
- **DB counter + inter-send sleep (chosen)** — proactive alerting before the wall, plus a simple sleep-based rate limit that requires zero extra infrastructure.

**Chosen Solution:**
- **Inter-send delay:** After each successful send and its SQS deletion, the worker sleeps `EMAIL_SEND_DELAY_SECONDS` (default `0.25 s`, ≈ 4 emails/s) before processing the next message. The sleep is `await asyncio.sleep()` — it yields to the event loop, not blocking anything. It sits _after_ `delete_message` so the SQS message is freed before the pause.
- **Quota tracking:** `email_quota` table (date PK, count). After each successful send, `increment_and_alert()` upserts today's row and reads the month-to-date sum. Log events fire at 50 %, 75 %, 90 %, and 100 % of both the daily and monthly limits — `WARNING` up to 75 %, `CRITICAL` from 90 %. No hard stop; Resend's own 429 is the backstop.
- **Configuration** (all overridable via SSM / env):

| Setting | Default | Purpose |
|---|---|---|
| `EMAIL_DAILY_LIMIT` | `100` | Free-tier daily ceiling |
| `EMAIL_MONTHLY_LIMIT` | `3000` | Free-tier monthly ceiling |
| `EMAIL_SEND_DELAY_SECONDS` | `0.25` | Inter-send pause in worker |

**Scaling path (if/when upgrading Resend plan):**
1. Set `EMAIL_DAILY_LIMIT` and `EMAIL_MONTHLY_LIMIT` to match the paid plan in SSM — alerts rescale automatically.
2. Reduce or zero out `EMAIL_SEND_DELAY_SECONDS` to remove the throughput cap (Resend Pro allows much higher burst).
3. If multiple worker instances are ever needed, the sleep-based throttle no longer gives a global rate limit — replace it with a Redis token bucket shared across workers (each worker acquires a token before sending, with a refill rate of `1 / EMAIL_SEND_DELAY_SECONDS` tokens/s). The `email_quota` counter logic is already multi-instance safe because it uses a Postgres upsert (`ON CONFLICT DO UPDATE`) — no change needed there.

**Implementation:**
- `src/core/services/email_quota.py` — `increment_and_alert(session)`
- `src/core/tasks.py` — `send_email_task` calls `increment_and_alert` after each successful send
- `src/worker.py` — sleep after `delete_message` for `send_email` tasks only
- `alembic/versions/e03b8aa073a3_add_email_quota_table.py` — creates `email_quota`

**Status:** ✅ Implemented

---

### 3. Async Background Jobs (Task Queue)

**Problem:** Standard HTTP requests must return quickly. Long-running tasks (like sending emails or processing files) will cause API timeouts and poor user experience.

**Decision:** Implement an asynchronous background worker using AWS SQS as the message broker and a long-polling Python worker.

**Chosen Solution:**
- **Broker:** AWS SQS (managed, durable, at-least-once delivery; visibility timeout = 300 s)
- **Worker:** `src/worker.py` — asyncio long-poll loop; SIGTERM-graceful; dispatches by `TASK_REGISTRY` key
- **Cron:** Nightly purge triggered by EventBridge Scheduler → SQS (not a cron inside the worker process)

**Implementation:**
- **Task Definition:** Async Python functions registered in `TASK_REGISTRY` in `src/core/tasks.py`.
- **Worker Process:** Separate Docker container (`worker`) runs `python -m src.worker` to consume from SQS.
- **API Integration:** Service layer calls `enqueue_*_task()` via `defer_after_commit()` — tasks enqueue after the DB transaction commits, preventing phantom messages on rollback. Endpoints return their normal status codes immediately.
- **Local Dev:** `SQS_QUEUE_URL` unset → tasks run inline (no queue needed).
- **Resilience:** SQS at-least-once delivery; tasks are written to be idempotent. Dead-letter queue captures repeated failures.

**Status:** ✅ Implemented

---

### 4. Containerization Strategy

**Problem:** Need consistent runtime environment across all stages (Dev, Test, Prod) to avoid "it works on my machine" issues.

**Decision:** Containerize the application using Docker with multi-stage builds for optimized image size.

**Implementation:**
- **Dockerfile:** Multi-stage build with Python 3.12 base image
- **docker-compose.yml:** Includes API service, PostgreSQL 16, and Mailpit (local SMTP on port 1025, web UI at :8025); worker is defined but commented out (runs inline in API process for local dev when `SQS_QUEUE_URL` is unset)
- **Health Checks:** Configured for all services
- **Volume Mounts:** Persistent data storage for PostgreSQL and local file storage

**Related Issues:**
- [#9](https://github.com/lahavrud/rs-recruiting/issues/9) - Containerize application with docker ✅ CLOSED

**Status:** ✅ Implemented

---

### 5. CI/CD Pipeline

**Problem:** Need automated quality checks, testing against a production-identical database, and safe deployment on every merge to main.

**Decision:** GitHub Actions with OIDC-based AWS authentication, a PostgreSQL service container for tests, and **continuous delivery to ECS** with a manual production gate. See [`release-process.md`](./release-process.md).

**Implementation:**
- **Workflows:** `.github/workflows/ci.yml` (checks) + `deliver.yml` / `_deploy.yml` / `rollback.yml` (delivery)
- **On pull_request to main:**
  - `lint`: Ruff linter + formatter + 5 custom validation scripts
  - `test`: Pytest against a PostgreSQL 16 service container (dialect parity with production)
  - `docker-build`: Build image and verify `/health` endpoint
- **On merge to main (after CI passes):** `deliver.yml` fires off CI completion → builds base+api+worker+alloy by SHA into the ops-account ECR → **pauses for manual approval** → deploys prod (`_deploy.yml`: gated migrate → roll web+worker → frontend) → auto-tags `vX.Y.Z` + creates the GitHub Release. _(Staging is retired for cost; the staging stage is preserved commented in `deliver.yml`.)_
- **Authentication:** GitHub Actions OIDC — per-environment deploy roles (no stored AWS credentials)
- **Deploy mechanism:** `_deploy.yml` rolls each ECS service via the `ecs-roll` action (render the live task-def with the new image → `aws-actions/amazon-ecs-deploy-task-definition` → wait for stability, circuit breaker armed). Terraform owns the task-def shape; CI owns only the image tag.
- **Validation Scripts:**
  - `validate_imports.py` - SOC enforcement (separation of concerns)
  - `check_file_sizes.py` - File size limits
  - `validate_type_hints.py` - Type hint validation
  - `validate_blocking_io.py` - Blocking I/O detection in async functions
  - `validate_test_files.py` - Test file existence checks

**Related Issues:**
- [#21](https://github.com/lahavrud/rs-recruiting/issues/21) - infra: ci/cd pipeline ✅ CLOSED
- [#80](https://github.com/lahavrud/rs-recruiting/issues/80) - chore(infra): Add type hints, blocking I/O, and test file validation to CI ✅ CLOSED
- [#97](https://github.com/lahavrud/rs-recruiting/issues/97) - deploy1: Production Deployment ✅ CLOSED

**Status:** ✅ Implemented

---

## Frontend Architecture

### 1. Frontend Architecture Decision

**Problem:** Roadmap mentions "Public Job Board" and "Admin Dashboard" but doesn't specify if FastAPI serves HTML or acts as headless API.

**Decision:** Use a separate SPA (Single Page Application) with FastAPI as a headless API.

**Options Considered:**

**A. Server-Side Rendering (SSR) with Jinja2**
- FastAPI serves HTML templates
- Simpler deployment (single service)
- SEO-friendly
- Less interactive, harder to scale frontend separately

**B. Separate SPA (React/Vue/Svelte)** ✅ **CHOSEN**
- FastAPI as headless API only
- Better UX, more interactive
- Separate deployment, CORS configuration needed
- Better for future mobile apps

**C. Hybrid (SSR + API)**
- FastAPI serves public pages (SSR)
- Admin/Company dashboards as SPA
- More complex but flexible

**Rationale:** Better separation of concerns, easier to scale frontend independently, better UX for dashboards.

**API Structure:** All endpoints return JSON. Frontend consumes REST API with JWT authentication.

**Implementation:**
- **Framework:** React 19 + TypeScript (via Vite)
- **Styling:** Tailwind CSS v4
- **Routing:** React Router v7
- **API Client:** Axios with JWT interceptors
- **Auth Flow:** JWT access token in `localStorage`, refresh token in HttpOnly cookie issued by backend. `AuthContext` resolves initial state synchronously from `localStorage` then verifies via `/api/auth/me`. Verified server-side on every request.
- **Dev Server:** Vite with proxy `/api/* → http://localhost:8000`

**Routes:**
| Path | Component | Guard | Description |
|------|-----------|-------|-------------|
| `/` | LandingPage | — | Public landing page |
| `/login` | LoginPage | — | JWT login form |
| `/register` | RegisterPage | — | Company self-registration (pending approval) |
| `/register-candidate` | RegisterCandidatePage | — | Candidate self-registration |
| `/activate` | ActivatePage | — | Activation-token handler (company + candidate) |
| `/forgot-password` | ForgotPasswordPage | — | Request password reset email |
| `/reset-password` | ResetPasswordPage | — | Set new password via reset token |
| `/about` | AboutPage | — | About the platform |
| `/contact` | ContactPage | — | Contact form |
| `/articles` | ArticlesIndexPage | — | Blog / articles listing |
| `/articles/:slug` | ArticlePage | — | Single article |
| `/jobs` | JobBoardPage | — | Published job listings (always public shell) |
| `/jobs/:id` | JobDetailPage | — | Single job detail |
| `/jobs/:id/apply` | ApplicationPage | — | Candidate application form (multipart upload) |
| `/dashboard` | DashboardPage | `ProtectedRoute` | Role-aware authenticated landing |
| `/admin/companies` | AdminCompaniesPage | `AdminRoute` | Manage companies + invites |
| `/admin/jobs` | AdminJobsPage | `AdminRoute` | Pending-job approval queue |
| `/admin/applications` | AdminApplicationsPage | `AdminRoute` | Application management |
| `/admin/candidates` | AdminCandidatesPage | `AdminRoute` | Candidate directory |
| `/company/jobs` | CompanyJobsPage | `CompanyRoute` | Company's own jobs |
| `/candidate/profile` | CandidateProfilePage | `CandidateRoute` | Edit profile + resume upload |
| `/candidate/applications` | CandidateApplicationsPage | `CandidateRoute` | Submitted applications list |
| `/candidate/applications/:id` | CandidateApplicationDetailPage | `CandidateRoute` | Single application detail |

**Project Structure:**
```
frontend/
├── src/
│   ├── components/
│   │   ├── guards/             # AdminRoute, CompanyRoute, CandidateRoute, ProtectedRoute
│   │   ├── layout/             # AppShell, Header, Sidebar, PublicHeader
│   │   ├── admin/              # Shared admin components (ActiveFilterChip, AdminField,
│   │   │                       #   AnimatedAccordion, FunnelIcon, MobileEntityCard, …)
│   │   └── ui/                 # Shared UI primitives (Button, Dialog, Eyebrow, FormField,
│   │                           #   StatusBadge, AutoGrowTextarea, PageHeader, …)
│   ├── pages/
│   │   ├── admin/
│   │   │   ├── components/     # Co-located dialogs, tabs, helpers per page
│   │   │   └── Admin*Page.tsx  # 4 admin pages — orchestration only (~200–800 lines each)
│   │   ├── company/            # CompanyJobsPage
│   │   ├── public/
│   │   │   ├── components/     # Co-located step/modal components for ApplicationPage
│   │   │   └── *.tsx           # LandingPage, JobBoardPage, JobDetailPage, ApplicationPage
│   │   ├── candidate/          # CandidateProfilePage, CandidateApplicationsPage, …
│   │   ├── ActivatePage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── LoginPage.tsx
│   │   └── RegisterPage.tsx
│   ├── utils/                  # formatDate, validation (EMAIL_RE/MOBILE_RE), apiError, …
│   ├── contexts/               # AuthContext
│   ├── styles/                 # forms.ts (inputCls, textareaCls, selectCls)
│   ├── locales/he/             # per-namespace Hebrew strings (common, auth, admin, …)
│   └── index.css               # Tailwind @theme tokens + color-scheme: dark
├── vite.config.ts
└── package.json
```

**Design system conventions** are documented in `CLAUDE.md` (Design System section). Key rules: use `<Button>` for all action buttons, `<Eyebrow>` for section labels, `<Field>` from `@/components/ui/Field` for form fields, and import `formatDate`/validation from `@/utils/`.

**Related Issues:**
- [#91](https://github.com/lahavrud/rs-recruiting/issues/91) - frontend1: Frontend Structure & Setup ✅ CLOSED
- [#92](https://github.com/lahavrud/rs-recruiting/issues/92) - frontend2: Public Pages ✅ CLOSED
- [#93](https://github.com/lahavrud/rs-recruiting/issues/93) - frontend3: Admin/Company dashboards ✅ CLOSED
- [#655](https://github.com/lahavrud/rs-recruiting/issues/655) - Decompose monolith pages + design system ✅ CLOSED

**Status:** ✅ Fully implemented and polished. Admin pages decomposed into co-located components. Design system primitives established.

---

### 2. CORS Configuration

**Problem:** With a separate SPA frontend, browsers enforce Same-Origin Policy. Frontend requests to backend API will be blocked unless CORS is properly configured.

**Decision:** Configure CORS middleware in FastAPI with environment-based origin whitelisting.

**Implementation:**
- **Middleware:** FastAPI `CORSMiddleware` in `src/main.py`
- **Configuration:** `ALLOWED_ORIGINS` environment variable (comma-separated list)
- **Default:** `http://localhost:3000` (development)
- **Security:** Never use wildcard (`*`) in production

**Configuration Requirements:**
- **Allowed Origins:** Environment-specific (dev/staging/prod)
- **Allowed Methods:** `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`
- **Allowed Headers:** `Content-Type`, `Authorization` (for JWT tokens)
- **Credentials:** `True` (to allow cookies/auth headers)

**Code Location:** `src/main.py` lines 27-34

**Related Issues:**
- Architecture decision documented in this file (no specific issue, part of frontend architecture)

**Status:** ✅ Implemented

---

## Backend Architecture

### 1. Service Layer Pattern

**Problem:** Business logic was mixed with API routes, making code harder to test and maintain.

**Decision:** Extract business logic into a dedicated service layer, keeping routers thin.

**Implementation:**
- **Structure:** `src/services/` directory with domain-specific services
- **Pattern:** Routers delegate to services, services contain business logic
- **Benefits:** Better testability, separation of concerns, reusable business logic

**Example Structure:**

```
src/
├── api/              # Thin routers (FastAPI endpoints) — one package per domain
│   ├── auth/         # login, registration, activation, password_reset, candidate_registration
│   ├── admin/        # companies, jobs, applications, candidates, invites, audit
│   ├── candidate/    # me, applications, data_export
│   ├── company/      # jobs, profile, resumes
│   └── public/       # job board, apply flow
└── services/         # Business logic — mirrors api/ layout
    ├── auth/
    ├── admin/
    ├── candidate/
    └── public/
```

**Related Issues:**
- [#41](https://github.com/lahavrud/rs-recruiting/issues/41) - refactor(services): Extract auth business logic into service layer ✅ CLOSED

**Status:** ✅ Implemented

---

### 2. Database Models & Schema

**Problem:** Need to implement domain models matching the architecture ERD.

**Decision:** Use SQLModel (SQLAlchemy + Pydantic) for database models with Alembic for migrations.

**Implementation:**
- **Models:** `src/models.py` with User, CompanyProfile, Job, CandidateProfile, Application
- **Enums:** `src/enums.py` with UserRole, JobStatus, ApplicationStatus
- **Schemas:** `src/schemas.py` with Pydantic schemas for API validation
- **Migrations:** Alembic for database schema versioning
- **Async:** Async SQLModel engine for async/await support

**Related Issues:**
- [#42](https://github.com/lahavrud/rs-recruiting/issues/42) - feat(models): Add Job, CandidateProfile, and Application models with relationships ✅ CLOSED
- [#23](https://github.com/lahavrud/rs-recruiting/issues/23) - feat: company onboarding (auth + db) ✅ CLOSED

**Status:** ✅ Implemented

---

### 3. Error Handling & Transaction Management

**Problem:** Race conditions and transaction rollback issues in user registration.

**Decision:** Implement proper error handling with explicit transaction rollbacks and IntegrityError handling.

**Implementation:**
- **Transaction Rollback:** Explicit `session.rollback()` on all error paths
- **IntegrityError Handling:** Catch database constraint violations and convert to domain exceptions
- **Error Types:** Custom exceptions in `src/services/exceptions.py`

**Related Issues:**
- [#47](https://github.com/lahavrud/rs-recruiting/issues/47) - fix(auth): Handle race condition in user registration (TOCTOU) ✅ CLOSED
- [#48](https://github.com/lahavrud/rs-recruiting/issues/48) - fix(auth): Add explicit transaction rollback on registration failure ✅ CLOSED

**Status:** ✅ Implemented

---

## Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    User ||--o| CompanyProfile : owns
    User ||--o| CandidateProfile : "linked (optional)"
    CompanyProfile ||--o{ Job : posts
    Job ||--o{ Application : receives
    CandidateProfile ||--o{ Application : submits

    %% Auth System (Admins, Companies, Candidates)
    User {
        int id
        string email
        string hashed_password
        enum role "ADMIN, COMPANY, CANDIDATE"
        bool is_active "False until activated"
        int failed_login_attempts
        datetime locked_until
        datetime created_at
    }

    %% Company Data
    CompanyProfile {
        int id
        int user_id "FK to User"
        string name
        string logo_url
        string contact_person
        string contact_phone
        datetime created_at
    }

    %% Job Inventory
    Job {
        int id
        int company_id
        string title
        string description
        string requirements
        string location
        enum status "PENDING_APPROVAL, PUBLISHED, CLOSED"
        datetime created_at
        datetime updated_at
    }

    %% Candidate identity + consent record (Sprint 11)
    %% Anonymous leads have user_id=NULL; registered candidates link 1:1 to User
    CandidateProfile {
        int id
        int user_id "FK to User SET NULL, nullable"
        string full_name
        string email "UNIQUE"
        string phone "nullable"
        string linkedin_url "nullable"
        string resume_path "nullable"
        string resume_filename "nullable"
        string resume_hash "nullable"
        datetime consent_given_at "nullable"
        string consent_policy_version "nullable"
        string consent_ip "nullable"
        text consent_user_agent "nullable"
        datetime tos_accepted_at "nullable"
        string tos_version "nullable"
        datetime created_at
    }

    %% Match (Core Business Entity)
    %% Partial unique index on (job_id, candidate_id) WHERE status != WITHDRAWN
    Application {
        int id
        int job_id
        int candidate_id
        enum status "NEW, APPROVED_BY_ADMIN, REJECTED, HIRED, WITHDRAWN"
        text admin_notes "nullable, internal only"
        text service_concept "nullable"
        text salary_expectations "nullable"
        text strength "nullable"
        text growth_area "nullable"
        string resume_path "nullable, per-application snapshot"
        string resume_filename "nullable"
        string resume_hash "nullable"
        datetime created_at
        datetime updated_at
    }

```

**Key Relationships:**

* `User` 1:1 `CompanyProfile` (one user owns one company profile)
* `User` 1:1 `CandidateProfile` (optional — anonymous leads have no linked User; FK is SET NULL on User delete)
* `CompanyProfile` 1:N `Job` (one company posts many jobs)
* `Job` 1:N `Application` (one job receives many applications)
* `CandidateProfile` 1:N `Application` (one candidate submits many applications)

**Status:** ✅ Implemented

---

## Deployment & DevOps

### 1. Database Backup Strategy

**Problem:** Production will use PostgreSQL. Docker volumes are insufficient for production safety. Need automated backup strategy to prevent data loss.

**Decision:** Use managed PostgreSQL service with automated backups for staging/production.

**Options Considered:**

* **Automated PostgreSQL Backups** – pg_dump scheduled via cron/kubernetes job
* **Managed Database Service** ✅ **CHOSEN** – AWS RDS Managed DB (built-in backups)
* **Point-in-Time Recovery** – WAL archiving for PostgreSQL
* **Backup to S3** – Store dumps in object storage

**Recommendation:**

* **Development:** Manual backups or Docker volume snapshots
* **Staging/Production:** Use managed PostgreSQL (RDS/DO) with automated daily backups + point-in-time recovery
* **Backup Retention:** 7 days daily, 4 weeks weekly, 12 months monthly

**Implementation Requirements:**

* Document backup/restore procedures
* Test restore process regularly
* Monitor backup success/failure
* Store backups in separate region/account

**Related Issues:**

* [#94](https://github.com/lahavrud/rs-recruiting/issues/94) - devops1: Database Backup Strategy ✅ CLOSED

**Status:** ✅ Implemented — RDS automated backups active (production)

---

### 2. Production Infrastructure

**Decision:** ECS Fargate services (web + worker) behind CloudFront, with managed RDS PostgreSQL. _(Originally a single EC2 host running Docker Compose; migrated to ECS Fargate on 2026-06-30 — see the INFRASTRUCTURE.md decisions log. Exact resource IDs for the ECS layer live in the infra repo / live AWS; this section is the higher-level shape.)_

**Architecture:**

```
Internet (HTTPS)
      │
Cloudflare (DNS only, grey-cloud — no proxy)
      │
CloudFront distribution (d2ghcom3efd3zg.cloudfront.net)
  ├── Lambda@Edge viewer-request  ← bot/crawler detection → FastAPI OG prerender
  ├── Default behavior            ← S3 origin (frontend SPA bundle, 3-day lifecycle)
  └── /api/* /auth/* /health      ← ECS web service origin
        │
ECS Fargate (cluster rs-recruiting-prod, us-east-1)
  ├── web service     ← FastAPI + alloy sidecar (image from ops-account ECR)
  └── worker service  ← SQS worker, same image family (python -m rs_worker.worker)
        │
RDS PostgreSQL db.t3.micro  ← private subnets, encrypted at rest
S3 rs-recruiting-app       ← file uploads
S3 rs-recruiting-frontend  ← SPA bundle (CloudFront default origin)
ECR (ops account)          ← Docker image registry, pulled cross-account
AWS SQS rs-recruiting-tasks ← async task queue (email sends, data exports, retention purge)
```

**AWS Resources:** (conceptual — see [`INFRASTRUCTURE.md`](./INFRASTRUCTURE.md) for the authoritative inventory, which is pending its post-ECS audit pass)

| Resource | Identifier | Purpose |
|---|---|---|
| CloudFront | `d2ghcom3efd3zg.cloudfront.net` | CDN + TLS termination, S3 + ECS origins |
| ACM | `arn:aws:acm:us-east-1:892512306022:certificate/d0e1d1f5-…` | TLS cert for rs-recruiting.com + www |
| ECS Fargate | cluster `rs-recruiting-prod` (`-web` / `-worker` services) | API + worker, behind CloudFront |
| RDS | `rs-recruiting-prod-db` | PostgreSQL 16, private subnets |
| S3 | `<APP_BUCKET>` + `rs-recruiting-frontend` | Uploads + frontend bundle |
| ECR (ops account) | `rs-recruiting/{api,worker,alloy}` | Docker images, pulled cross-account |
| SQS | `rs-recruiting-tasks` | Async task queue for worker |
| IAM Role (CI) | per-environment OIDC deploy roles | ECR push (ops), ECS deploy, S3/CloudFront |

**Domain:** `rs-recruiting.com` — DNS in Cloudflare (grey-cloud, DNS only). TLS terminates at CloudFront via ACM certificate (`us-east-1`). Cloudflare proxying intentionally disabled — CloudFront handles CDN and certificate.

**Configuration:** Runtime secrets in AWS SSM Parameter Store under `/rs-recruiting/prod/`, read by the ECS task at startup (no `.env` materialized on a host). Non-secret config rides the task definition.

**Related Issues:**

* [#97](https://github.com/lahavrud/rs-recruiting/issues/97) - deploy1: Production Deployment ✅ CLOSED

**Status:** ✅ Live at https://rs-recruiting.com

---

### 3. Environment Deployment Strategy

**Decision:** Trunk-based **continuous delivery** (since 2026-06-30). CI validates everything (lint → test → docker-build); a green merge to `main` builds the image and promotes it to **production** behind a single manual approval (`production` GitHub Environment required reviewer). See [`release-process.md`](./release-process.md).

**Environments:**

1. **Development** – Local Docker Compose (`docker-compose.yml`) with PostgreSQL
2. **Production** – Live at `https://rs-recruiting.com`, deployed from the SHA-tagged image after manual approval (see Production Infrastructure above)

**Staging:** retired for cost (was an on-demand scale-to-zero ECS env). The staging stage is preserved (commented) in `deliver.yml` and `_deploy.yml` is environment-agnostic, so it can be re-enabled later; pre-prod risk is covered by CI + the prod approval gate + fast `rollback.yml`.

**CI Gate:** lint + test (PostgreSQL) + docker-build smoke test — catch prod-specific issues before the build/deliver pipeline runs.

**Status:** ✅ Production live · 🧊 Staging deferred (infra + workflow preserved)

---

## Code Quality & Standards

### 1. Pre-commit Hooks

**Problem:** Need to enforce code quality and security standards before code reaches the repository.

**Decision:** Implement comprehensive pre-commit hooks for code quality, security, and commit message validation.

**Implementation:**

* **File Quality:** Trailing whitespace, end-of-file, YAML/JSON validation
* **Security:** detect-secrets to prevent credential commits
* **Commit Messages:** Conventional Commits format validation
* **Linting:** Ruff auto-fix enabled
* **Secrets Baseline:** Baseline file for false positives

**Related Issues:**

* [#75](https://github.com/lahavrud/rs-recruiting/issues/75) - chore(infra): Enhance pre-commit hooks configuration ✅ CLOSED

**Status:** ✅ Implemented

---

### 2. Code Validation Standards

**Problem:** Need automated validation to enforce code quality standards and prevent common issues.

**Decision:** Implement validation scripts in CI to check for:

* Type hints on public functions
* Blocking I/O in async functions
* Test file existence (matching source structure)
* Import patterns (SOC enforcement)
* File size limits

**Implementation:**

* **Scripts:** `scripts/validate_*.py` for various validations
* **CI Integration:** All validations run in CI `lint` job
* **Fast Execution:** All validations run in < 5 seconds

**Related Issues:**

* [#80](https://github.com/lahavrud/rs-recruiting/issues/80) - chore(infra): Add type hints, blocking I/O, and test file validation to CI ✅ CLOSED

**Status:** ✅ Implemented

---

## Decision Log

This section tracks when decisions were made and implemented:

| Decision | Issue | Status | Date |
|----------|-------|--------|------|
| File Storage Strategy | [#43](https://github.com/lahavrud/rs-recruiting/issues/43) | ✅ Implemented | - |
| Email/Notification Service | [#44](https://github.com/lahavrud/rs-recruiting/issues/44) | ✅ Implemented | - |
| Async Background Jobs | Architecture doc | ✅ Implemented | - |
| Containerization | [#9](https://github.com/lahavrud/rs-recruiting/issues/9) | ✅ Implemented | - |
| CI/CD Pipeline | [#21](https://github.com/lahavrud/rs-recruiting/issues/21), [#97](https://github.com/lahavrud/rs-recruiting/issues/97) | ✅ Implemented | 2026-04-23 |
| Frontend Architecture | Architecture doc | ✅ Implemented | - |
| CORS Configuration | Architecture doc | ✅ Implemented | - |
| Service Layer Pattern | [#41](https://github.com/lahavrud/rs-recruiting/issues/41) | ✅ Implemented | - |
| Database Models | [#42](https://github.com/lahavrud/rs-recruiting/issues/42) | ✅ Implemented | - |
| Error Handling | [#47](https://github.com/lahavrud/rs-recruiting/issues/47), [#48](https://github.com/lahavrud/rs-recruiting/issues/48) | ✅ Implemented | - |
| Production Infrastructure | [#97](https://github.com/lahavrud/rs-recruiting/issues/97) | ✅ Live | 2026-04-23 |
| Database Backup Strategy | [#94](https://github.com/lahavrud/rs-recruiting/issues/94) | ✅ Implemented (RDS automated backups) | - |
| Candidate Authentication | [#604](https://github.com/lahavrud/rs-recruiting/issues/604) | ✅ Implemented | 2026-05 |
| Staging Environment | [#95](https://github.com/lahavrud/rs-recruiting/issues/95), [#96](https://github.com/lahavrud/rs-recruiting/issues/96) | 🧊 Icebox | - |
| Pre-commit Hooks | [#75](https://github.com/lahavrud/rs-recruiting/issues/75) | ✅ Implemented | - |
| Code Validation | [#80](https://github.com/lahavrud/rs-recruiting/issues/80) | ✅ Implemented | - |

---

## Future Considerations

Potential future architectural decisions:

1. **Candidate Application Editing & Withdrawal** – Allow candidates to edit or retract submitted applications (#610).
2. **GDPR Right-to-Erasure** – Candidate-initiated account deletion flow (#615).
3. **Advanced Matching / Notifications** – Candidate job-match alerts, company candidate-match suggestions.
4. **Microservices** – Currently a monolith. Only warranted if separate scaling or team boundaries emerge.
5. **Caching Strategy** – No cache layer; Redis was removed when the task queue moved to SQS. Add back only if hot-path latency becomes an issue.
6. **API Versioning** – No versioning today; add if a breaking public API is needed.

---

## References

* [GitHub Issues](https://github.com/lahavrud/rs-recruiting/issues) - All architecture-related issues
* [CLAUDE.md](../CLAUDE.md) - Developer guide, design system, conventions, and running locally
* [GitHub Organization](GITHUB_ORGANIZATION.md) - Issue templates and project management
* [Retention Purge Runbook](RETENTION_PURGE.md) - Candidate data retention background job
