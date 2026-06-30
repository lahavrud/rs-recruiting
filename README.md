# RS Recruitment

A full-stack recruitment CRM built for a boutique agency. Manages the full pipeline from company onboarding and job posting through candidate applications to admin-gated match decisions — with a dark luxury React frontend served over a production AWS stack.

**Live:** [rs-recruiting.com](https://rs-recruiting.com)

<img src="docs/screenshots/apply-flow.gif" width="700" alt="Landing page and public job board" />
<p><em>Public-facing site — landing page, job board, and candidate application flow</em></p>

<img src="docs/screenshots/admin-dashboard.png" width="650" alt="Admin dashboard" />
<p><em>Admin dashboard — live stats across companies, jobs, applications, and candidates with quick-action shortcuts</em></p>

---

## Features

**Public**
- Job board with per-job detail pages and JSON-LD `JobPosting` structured data
- Candidate application form with resume upload (PDF/DOCX → S3)
- GDPR-style consent tracking: timestamp, policy version, IP, user-agent stored per submission
- SEO: dynamic sitemap.xml, robots.txt, Open Graph meta, server-side prerendered OG pages

**Admin**
- Invite-based company onboarding (token → registration → approval → activation)
- Job approval queue (review, approve, or reject postings)
- Application management with status tracking (New → Approved → Hired/Rejected/Withdrawn)
- Candidate directory with profile and resume access
- Append-only audit log: every admin action is recorded with actor, target, IP, and timestamp

**Company**
- Job posting and management dashboard
- View applications per job

**Candidate**
- Self-registration with email verification (2-hour activation window)
- Profile management (name, phone, LinkedIn URL, resume upload)
- View submitted applications and their status
- GDPR data export (profile + per-application resumes as ZIP)
- Password reset (forgot-password → email link → reset flow)

**Auth**
- JWT access token (10 min) + HttpOnly refresh cookie (7 days)
- Role-based route guards (ADMIN / COMPANY / CANDIDATE / public)
- Account lockout after 5 failed attempts (15-min cooldown, database-backed)
- Refresh token rotation: single-use tokens deleted on use, logout, or password reset

---

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, React Router v7 |
| Backend | FastAPI, SQLModel (SQLAlchemy + Pydantic), Alembic, Python 3.12 |
| Database | PostgreSQL 16, asyncpg (connection pool + pre-ping) |
| Background Jobs | AWS SQS + custom Python worker, EventBridge Scheduler (nightly purge) |
| File Storage | AWS S3 (production), local filesystem (dev) — provider abstraction |
| Email | Resend via SMTP relay (production) — provider abstraction; 10+ HTML templates |
| Auth | JWT (PyJWT), bcrypt, HttpOnly refresh cookie, slowapi rate limiting |
| Observability | Sentry (backend + frontend with source maps), Google Tag Manager, CloudWatch |
| Infrastructure | ECS Fargate + RDS + S3 + SQS + ECR + SSM + CloudFront, Cloudflare (DNS only) |
| CI/CD | GitHub Actions — OIDC auth, change detection, Pytest against PostgreSQL, continuous delivery to ECS with a manual prod gate |
| Code Quality | Ruff, ESLint, TypeScript strict, 5 custom validation scripts, weekly pip-audit |

---

## Architecture

<img src="docs/screenshots/aws-architecture.png" width="750" alt="AWS architecture diagram" />

<p><em>Request path: Users → Cloudflare (DNS only) → CloudFront → S3 (frontend SPA) or the ECS Fargate web service via API/auth/health behaviors (Lambda@Edge handles bot detection for OG prerender). Background jobs: SQS → ECS Fargate worker service. CI/CD path: GitHub Actions → S3 (frontend bundle) + ECR (Docker images, ops account) → ECS deploy. Observability: CloudWatch alarms → SNS ops-alerts; Inspector2 scanning ECR images. All secrets live in SSM Parameter Store as SecureStrings.</em></p>

### Data model

```mermaid
erDiagram
    User ||--o| CompanyProfile : owns
    User ||--o| CandidateProfile : "linked (optional)"
    CompanyProfile ||--o{ Job : posts
    Job ||--o{ Application : receives
    CandidateProfile ||--o{ Application : submits

    User {
        int id
        string email
        string hashed_password
        enum role "ADMIN, COMPANY, CANDIDATE"
        bool is_active
    }
    CompanyProfile {
        int id
        int user_id
        string name
        string logo_url
    }
    Job {
        int id
        int company_id
        string title
        enum status "PENDING_APPROVAL, PUBLISHED, CLOSED"
    }
    CandidateProfile {
        int id
        int user_id "nullable — anonymous leads have no linked User"
        string full_name
        string email
        string resume_path
        datetime consent_given_at
    }
    Application {
        int id
        int job_id
        int candidate_id
        enum status "NEW, APPROVED_BY_ADMIN, REJECTED, HIRED, WITHDRAWN"
        text admin_notes
    }
```

---

## Design Decisions

**Three-tier authentication** — Admins, companies, and candidates are all full authenticated roles (ADMIN, COMPANY, CANDIDATE). Admins approve company invites; companies post jobs; candidates self-register, activate via email, and claim their applications. The schema distinguishes authenticated candidates (`user_id` linked) from anonymous leads (applications submitted before registration), enabling a seamless "register and claim" flow without breaking legacy data.

**Stateless JWT with short-lived access tokens** — Access tokens have a 10-minute TTL; refresh tokens are single-use and deleted from the database on logout or refresh. There is no blacklist — the short TTL serves as the post-logout tolerance window. Refresh token rotation (delete consumed token, issue new pair) prevents replays. Failed login attempts and account lockout are tracked on the `User` row with a `locked_until` timestamp.

**Storage and email abstraction** — Both file storage and email are behind provider interfaces. A single env var switches between local/S3 for storage with no code changes. Email providers can be SES or SMTP; production uses Resend via SMTP relay. This made local development cheap and production deployment straightforward.

**Async task queue with AWS SQS** — Sending email from inside a request handler risks timeouts and drops on provider throttling. All outbound email is pushed to an SQS queue and processed by a separate worker service (`rs_worker/worker.py`) with retry logic. Ten transactional email templates cover the full company and candidate lifecycle. The `defer_after_commit` pattern ensures tasks are enqueued only after the originating transaction commits, preventing phantom messages on rollback.

**OIDC-based continuous delivery with change detection** — GitHub Actions authenticates to AWS via OIDC (no stored credentials). A `detect-changes` job skips irrelevant work — a docs-only PR never runs backend tests or builds Docker. Every commit that lands on `main` and passes CI is built once (tagged by SHA, pushed to the ops-account ECR), then promoted to production behind a manual approval (a `production` GitHub Environment required reviewer). The prod roll runs a gated DB migration first and waits for service stability with the deployment circuit breaker armed.

**Custom CI validation scripts** — Beyond Ruff and TypeScript, five custom scripts run in CI: SOC import enforcement (services must not import FastAPI), blocking I/O detection in async functions (catches `open()`, `requests.*`, `time.sleep()`), type hint coverage on public functions, test file existence checks (1:1 mapping with source files), and file size limits. Catches architecture drift that standard linters miss.

**Docker hardening** — Multi-stage build with layer caching on the lockfile. Runtime image runs as a non-root `appuser` (permissions fixed in entrypoint script). Dev and test dependencies are excluded. Health check hits the `/health` endpoint via the same proxy path a real client uses.

**SEO prerendering for a SPA** — Client-side React can't be indexed for job-specific pages. The backend generates server-side HTML snapshots with full Open Graph meta, canonical URLs, and JSON-LD `JobPosting` structured data (title, salary range, location, dates). A dynamic sitemap.xml lists all published jobs with `lastmod` from `updated_at`. Googlebot gets a real HTML response; users get the SPA.

**Hebrew-only RTL UI** — The entire frontend is in Hebrew with `<html dir="rtl">` forced globally. All UI strings live in per-namespace JSON files under `locales/he/` (13 files, one per feature area); raw backend error strings are never surfaced to the user.

---

## Testing

70+ test files, ~18k lines, parallel execution via `pytest-xdist` (each worker gets a dedicated database).

```
tests/
├── models/           # ORM model validation
├── services/         # Business logic (auth, admin, company, public, candidate flows)
├── api/              # Endpoint tests (SEO, rate limiting, request handling)
├── templates/        # Email template rendering
└── core/
    ├── services/     # Email, storage, file validation
    └── infrastructure/  # Database, config, security, transactions, rate limiting
```

Notable coverage: full auth lifecycle (invite → registration → approval → activation → login → lockout → logout), candidate registration and activation, SEO output (sitemap, JSON-LD, OG prerender), SQS task enqueue/handling (email, data export, candidate purge), storage abstraction, database transactions and rollback guarantees.

```bash
uv run pytest -n auto
```

---

## Local Development

**Prerequisites:** Python 3.12+, [uv](https://github.com/astral-sh/uv), Docker + Docker Compose, Node 18+

```bash
# 1. Clone and install
git clone https://github.com/lahavrud/rs-recruiting.git
cd rs-recruiting
uv sync

# 2. Start services (PostgreSQL + Mailpit local SMTP)
docker-compose up -d

# 3. Run migrations
uv run alembic upgrade head

# 4. Start backend
uv run uvicorn src.main:app --reload

# 5. Start frontend (separate terminal)
cd frontend
npm install
npm run dev
```

The frontend proxies `/api/*` to `http://localhost:8000`. Outbound email goes to [Mailpit](http://localhost:8025) — no provider account needed in development. Tasks (email, exports) run inline in the API process when `SQS_QUEUE_URL` is unset.

### Environment

```bash
# Minimum required
export JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
```

Production env vars (AWS credentials, Sentry DSN, Resend SMTP credentials, S3 bucket) are only needed outside local dev — the defaults in `docker-compose.yml` cover everything for local work.

### Linting

```bash
uv run ruff check . && uv run ruff format --check .
cd frontend && npx tsc --noEmit && npm run lint
```

---

## Project Structure

```
rs-recruiting/
├── src/
│   ├── api/          # Thin FastAPI routers (auth, admin, company, public, seo)
│   ├── services/     # Business logic, decoupled from routers
│   │   ├── auth/     # session, registration, activation, password_reset, candidate_registration, password_change
│   │   ├── admin/    # companies, jobs, applications, candidates, invites, audit
│   │   ├── company/  # jobs, profile, candidates
│   │   └── utils/    # audit logging, contract PDF, legal text
│   ├── core/         # Infrastructure abstractions: storage, email, task queue definitions
│   ├── models.py     # SQLModel ORM models
│   ├── templates/    # Transactional email templates (HTML)
│   └── worker.py     # SQS worker — polls queue and dispatches to task registry
├── frontend/src/
│   ├── pages/        # public/, admin/, company/, candidate/ + auth pages
│   ├── components/   # layout/, guards/, ui/ — shared React components
│   ├── hooks/        # useAuth, useInfiniteList, useDebounce, usePageTitle…
│   └── locales/he/   # per-namespace translation files (common, auth, admin, …)
├── tests/            # 70+ test files, pytest-xdist parallel execution
├── scripts/          # 5 CI validation scripts
├── docs/             # Architecture decisions, API design, infrastructure, runbooks
└── .github/workflows/
    ├── ci.yml        # Lint, test, docker-build (change-aware)
    ├── deliver.yml   # Build by SHA → manual approval → prod → tag
    ├── _deploy.yml   # Reusable per-environment ECS deploy (migrate → roll → frontend)
    ├── rollback.yml  # Re-point an ECS service to its previous task-def revision
    └── security-audit.yml  # Weekly pip-audit for CVEs
```
