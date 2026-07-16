# Contributing to rs-recruiting

## Setup

```bash
# Backend — install the workspace, start backing services, run the API
uv sync
make services                                # Postgres + Mailpit + LocalStack
uv run uvicorn rs_api.main:app --reload      # tasks run inline while SQS is unset

# Frontend
cd frontend && npm install && npm run dev
```

Requires: Python 3.12+, Node 22+, Docker + Compose. The schema is created from
SQLModel metadata on startup — don't run `alembic upgrade` against a local DB
(the migration chain assumes an existing prod schema).

---

## Board workflow

Issues live on the [project board](https://github.com/users/lahavrud/projects/1). Every issue moves through statuses as work progresses — don't skip steps, it's how we track what's in flight.

```
Backlog → In Progress → In Review → Done
               ↕              ↕
            Blocked        Blocked
```

| Status | When to set it |
|---|---|
| **Backlog** | Exists and is real, but not actively being worked. Default state for all new issues. |
| **In Progress 🏗️** | Branch is open. Move here when you cut the branch, not when you start coding. |
| **In Review 🔍** | PR is open. The handoff signal — tells the other person their attention is needed. |
| **Done ✅** | Set automatically when the PR merges via `Closes #NNN` in the PR body. Never set manually. |
| **Blocked ⛔** | Can't proceed. Comment what's blocking and who needs to act, then move back to In Progress when unblocked. |

Deferred issues with no timeline get the `icebox` label and stay in Backlog — they won't auto-close.

**Rules:**
- Move to **In Progress** when you open the branch, not when you start coding.
- Move to **In Review** when you open the PR, not when it's approved.
- Never close an issue manually — `Closes #NNN` in the PR body does it on merge.
- Keep one active milestone at a time. Multiple milestones in progress simultaneously is a sign of too much context-switching.

---

## Issues

Use an issue template — choose the one that fits (Bug Report, Feature Request, Infrastructure Task, Task/Feature).

**Title format — Conventional Commits style:**
```
type(scope): short imperative description
```

| Type | Use for |
|---|---|
| `feat` | New user-facing capability |
| `fix` | Bug fix |
| `chore` | Maintenance, config, tooling |
| `refactor` | Code restructuring without behavior change |
| `test` | Test additions or changes |
| `docs` | Documentation only |
| `ci` | CI/CD workflow changes |

Examples:
```
feat(auth): add refresh token reuse detection
fix(candidates): apply endpoint accepts non-published jobs
chore(deps): update FastAPI to 0.115
```

**Labels:** every issue gets a type label (`feat`, `fix`, `chore`, …) and a priority label (`P1`, `P2`, `P3`). Add a domain label (`backend`, `frontend`, `infra`, …) when it helps filter.

**Milestone:** assign when triaging. If there's no clear milestone yet, leave it in Backlog without one — but don't leave it there indefinitely or it will go stale.

---

## Branches

```
type/short-kebab-summary
```

Types mirror commit types: `feat`, `fix`, `chore`, `refactor`, `docs`, `hotfix`.

```bash
git checkout -b feat/refresh-token-reuse-detection
git checkout -b fix/apply-published-jobs-guard
git checkout -b chore/update-fastapi
```

---

## Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): short description
```

- Subject line ≤ 72 characters, imperative mood ("add", not "adds" or "added")
- No period at the end
- Add a body if the *why* isn't obvious from the title

---

## Pull requests

Use the PR template — all five sections are required (write `N/A` if a section doesn't apply).

The **Related Issue** line must include `Closes #NNN`. This auto-closes the issue and moves it to **Done** on the board when the PR merges.

Before opening a PR:

```bash
# Backend
uv run ruff check . && uv run ruff format --check .

# Frontend
cd frontend && npx tsc --noEmit && npm run lint
```

CI must pass and **@lahavrud** must approve before merge (enforced by the branch ruleset + CODEOWNERS). Squash merge only — the PR title becomes the commit message, so make it a valid Conventional Commit.

---

## Sensitive areas

Changes to these paths have non-obvious invariants. Read carefully before touching:

| Path | Risk |
|---|---|
| `libs/shared/rs_shared/services/auth/` | JWT lifecycle, token rotation, lockout logic |
| `alembic/` | Irreversible DB migrations. Never squash or delete applied migrations. |
| `libs/shared/rs_shared/models.py` | Schema changes ripple everywhere |
| `.github/workflows/` | CI/CD — bad changes reach production |

When in doubt, open a draft PR and ask for early review.
