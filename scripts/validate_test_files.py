#!/usr/bin/env python3
"""Validate the 1:1 mapping between source files and test files.

Enforces two invariants:
- Every src/<dir>/X.py has a matching tests/<dir>/test_X.py (forward check)
- Every tests/<dir>/test_X.py has a matching src/<dir>/X.py (reverse check)

The reverse check catches orphan test files left behind after a source file
is renamed, split, or deleted.
"""

import sys
from pathlib import Path

# Mapping of source directories to test directories
SOURCE_TO_TEST_MAPPING = {
    "src/services": "tests/services",
    "src/api": "tests/api",
    "src/core/infrastructure": "tests/core/infrastructure",
    "src/templates": "tests/templates",
}

# Source files that don't require tests (exceptions, simple factories, etc.)
EXCLUDED_SOURCE_FILES: set[str] = {
    # src/api/seo/ is a package whose internal modules (_jsonld, _render, etc.)
    # are exercised end-to-end by tests/api/test_seo.py — the integration tests
    # cover every path through the package via real HTTP responses. Per-module
    # unit tests would duplicate the integration coverage; the package was split
    # only to satisfy the 200-line file cap, not for test isolation.
    "src/api/seo/_articles.py",
    "src/api/seo/_content.py",
    "src/api/seo/_jsonld.py",
    "src/api/seo/_pages.py",
    "src/api/seo/_render.py",
    "src/api/seo/_routes.py",
    "src/api/seo/_sitemap.py",
    # Two version-string constants (no logic to test).
    "src/services/utils/legal.py",
    # Sprint 11 / #606 — helper modules split out of applications.py to
    # satisfy file-size caps. Exercised end-to-end via
    # tests/services/public/test_applications.py and
    # tests/api/public/test_applications.py respectively.
    "src/services/public/_application_helpers.py",
    "src/api/public/_apply_handler.py",
    # Sprint 11 / #609 — shared resume-streaming helper imported by both
    # the admin (src/api/company/resumes.py) and candidate-facing
    # (src/api/candidate/applications.py) resume endpoints. Exercised
    # end-to-end via the consumer endpoints' tests.
    "src/api/_resume_streaming.py",
    # Helper modules split out of admin service files to satisfy the 300-line
    # file cap. Exercised end-to-end via tests/services/admin/test_candidates.py,
    # test_applications.py, and test_jobs.py respectively.
    "src/services/admin/_candidates_purge.py",
    "src/services/admin/_application_status.py",
    "src/services/admin/_job_close.py",
    # OTel SDK initialisation — thin wrappers around TracerProvider,
    # MeterProvider, and LoggerProvider. No domain logic; exercised
    # end-to-end by every request/task that emits telemetry in prod.
    "src/core/infrastructure/telemetry.py",
}

# Test files allowed to exist without a matching source file.
# Use this only for cross-cutting behavioral tests that don't map to a single
# module (e.g. fail-closed behavior that spans multiple infrastructure pieces).
EXCLUDED_TEST_FILES: set[str] = {
    # Verifies system-wide fail-closed behavior when Redis is unavailable;
    # exercises code paths across security + dependencies, not a single module.
    "tests/core/infrastructure/test_redis_fail_closed.py",
    # Integration tests for the src/api/seo/ package — exercises all internal
    # modules via real HTTP. The package's internal _*.py files are listed in
    # EXCLUDED_SOURCE_FILES above for the same reason.
    "tests/api/test_seo.py",
}


def get_expected_test_file(source_file: Path) -> Path | None:
    """Get the expected test file path for a source file."""
    source_str = str(source_file)

    for source_dir, test_dir in SOURCE_TO_TEST_MAPPING.items():
        if source_str.startswith(source_dir):
            relative_path = source_file.relative_to(source_dir)
            test_file_name = f"test_{relative_path.name}"
            return Path(test_dir) / relative_path.parent / test_file_name

    return None


def get_expected_source_file(test_file: Path) -> Path | None:
    """Get the expected source file path for a test file."""
    test_str = str(test_file)

    for source_dir, test_dir in SOURCE_TO_TEST_MAPPING.items():
        if test_str.startswith(test_dir):
            relative_path = test_file.relative_to(test_dir)
            # test_X.py -> X.py
            if not relative_path.name.startswith("test_"):
                return None
            source_file_name = relative_path.name[len("test_") :]
            return Path(source_dir) / relative_path.parent / source_file_name

    return None


def check_missing_test_files() -> list[str]:
    """Find source files without a matching test file."""
    violations: list[str] = []
    src_path = Path("src")

    if not src_path.exists():
        return [f"Source directory '{src_path}' not found"]

    for source_dir in SOURCE_TO_TEST_MAPPING:
        dir_path = Path(source_dir)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue

            file_str = str(py_file).replace("\\", "/")
            if file_str in EXCLUDED_SOURCE_FILES:
                continue

            expected_test = get_expected_test_file(py_file)
            if expected_test is None:
                continue

            if not expected_test.exists():
                violations.append(f"{py_file}: Missing test file '{expected_test}'")

    return violations


def check_orphan_test_files() -> list[str]:
    """Find test files without a matching source file."""
    violations: list[str] = []

    for test_dir in SOURCE_TO_TEST_MAPPING.values():
        dir_path = Path(test_dir)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("test_*.py"):
            file_str = str(py_file).replace("\\", "/")
            if file_str in EXCLUDED_TEST_FILES:
                continue

            expected_source = get_expected_source_file(py_file)
            if expected_source is None:
                continue

            if not expected_source.exists():
                violations.append(
                    f"{py_file}: Orphan test file — no matching '{expected_source}'"
                )

    return violations


def main() -> None:
    missing = check_missing_test_files()
    orphans = check_orphan_test_files()

    if missing:
        print("❌ Missing test files detected:")
        print("Source files must have corresponding test files.\n")
        for v in missing:
            print(f"  {v}")

    if orphans:
        if missing:
            print()
        print("❌ Orphan test files detected:")
        print(
            "Test files must have a corresponding source file. "
            "Delete the test, restore the source, or whitelist the test in "
            "EXCLUDED_TEST_FILES if it is intentionally cross-cutting.\n"
        )
        for v in orphans:
            print(f"  {v}")

    if missing or orphans:
        sys.exit(1)

    print("✅ All source files have matching test files (and vice versa)")
    sys.exit(0)


if __name__ == "__main__":
    main()
