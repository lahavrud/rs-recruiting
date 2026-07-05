# PR Checklist

Run the full pre-PR validation suite for rs-recruiting.

## Steps

1. Run the canonical CI-parity suite (single source of truth — the `check` target in `Makefile`):

   ```bash
   make check
   ```

   It covers backend lint + format, import boundaries (`lint-imports` + `validate_imports.py`), the quality-gate scripts (`check_file_sizes`, `validate_type_hints`, `validate_blocking_io`, `validate_test_files`), frontend types + lint + tests, and the backend test suite. Make stops at the first failure.

   If `ruff format --check` fails, run `uv run ruff format .` to fix, then re-run.

2. Report a final summary:

   ```
   ✓/✗ backend lint + format
   ✓/✗ import boundaries
   ✓/✗ quality-gate scripts
   ✓/✗ frontend types + lint + tests
   ✓/✗ backend tests (N passed, N failed)
   ```

Do not proceed with PR creation if any check fails.
