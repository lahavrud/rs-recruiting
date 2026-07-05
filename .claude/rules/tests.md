# Test Rules

## Hard constraints
- **No network calls anywhere in `tests/`** — use the fixtures and fakes defined in `tests/conftest.py`
- **No cross-test imports** — tests import from the workspace packages (`rs_shared` / `rs_api` / `rs_worker`), never from other test files
- **1:1 source mapping** — every source module must have a corresponding test file (CI script `scripts/validate_test_files.py` enforces it). The mapping spans the workspace members; web-infra modules (`rs_api/infrastructure/`) map to `tests/api/infrastructure/`.

## Structure
A single top-level `tests/` tree covers all three workspace members:
```
tests/
├── models/           # ORM model validation
├── services/         # Business logic (rs_shared/services: auth, admin, company, public, candidate)
│   └── utils/        # Audit log, contract PDF generation
├── api/              # rs_api endpoint tests, mirroring the router packages
│   ├── admin/ auth/ candidate/ company/ public/
│   ├── infrastructure/  # rs_api/infrastructure: dependencies, error_handling, limiter, middleware
│   └── …             # analytics, sentry tunnel, SEO
├── templates/        # Email template rendering
├── conftest.py       # Shared fixtures, fakes (storage/email/SQS mocks), model factories
├── test_main.py  test_schemas.py
├── test_domain_is_framework_free.py  # guard: worker surface imports no web stack
└── core/
    ├── services/     # Email, storage, file validation, embeddings, cv_extraction
    └── infrastructure/  # DB, config, security, transactions, request_context
```

## Execution
```bash
uv run pytest -n auto              # full suite, parallel (each worker = dedicated DB)
scripts/test_fast.sh [args…]       # same, no coverage — fast dev loop, forwards extra args
uv run pytest tests/services/auth/ # single directory
uv run pytest -k "test_lockout"    # filter by name
uv run pytest -x                   # stop on first failure
make check                         # full CI-parity gate (lint + validators + both test suites)
```

## Patterns
- Database tests use the `session` fixture — never open a session manually
- SQS/S3/email use fakes — see `tests/conftest.py` for the fake implementations
- For async endpoints, use `AsyncClient` from `httpx` via the `client` fixture
- Factory helpers for model creation live in `tests/conftest.py`

## CI behaviour
Tests run with `uv sync --frozen --group test` + `pytest -n auto`. The `--frozen` flag means a stale `uv.lock` fails the build — always commit `uv.lock` after touching `pyproject.toml`.
