# Test Rules

## Hard constraints
- **No network calls anywhere in `tests/`** — use the fixtures and fakes defined in `tests/conftest.py`
- **No cross-test imports** — tests import from `src/`, never from other test files
- **1:1 source mapping** — every `src/` module must have a corresponding test file (CI script enforces this)

## Structure
```
tests/
├── models/           # ORM model validation
├── services/         # Business logic (auth, admin, company, public, candidate)
│   └── utils/        # Audit log, contract PDF generation
├── api/              # Endpoint tests (SEO, rate limiting, request handling)
├── templates/        # Email template rendering
├── conftest.py       # Shared fixtures, fakes (storage/email/SQS mocks), model factories
└── core/
    ├── services/     # Email, storage, file validation
    └── infrastructure/  # DB, config, security, transactions, rate limiting
```

## Execution
```bash
uv run pytest -n auto              # full suite, parallel (each worker = dedicated DB)
uv run pytest tests/services/auth/ # single directory
uv run pytest -k "test_lockout"    # filter by name
uv run pytest -x                   # stop on first failure
```

## Patterns
- Database tests use the `session` fixture — never open a session manually
- SQS/S3/email use fakes — see `tests/conftest.py` for the fake implementations
- For async endpoints, use `AsyncClient` from `httpx` via the `client` fixture
- Factory helpers for model creation live in `tests/conftest.py`

## CI behaviour
Tests run with `uv sync --frozen --group test` + `pytest -n auto`. The `--frozen` flag means a stale `uv.lock` fails the build — always commit `uv.lock` after touching `pyproject.toml`.
