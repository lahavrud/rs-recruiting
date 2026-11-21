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

# Mapping of source directories to test directories. Sources live in the uv
# workspace members (libs/shared, services/api, services/worker); tests stay in
# a single top-level tests/ tree. Mappings nest (core/ contains
# core/infrastructure/), so a file maps through its LONGEST matching source dir,
# not the first one listed, and each file is checked once.
SOURCE_TO_TEST_MAPPING = {
    "libs/shared/rs_shared/core": "tests/core",
    "libs/shared/rs_shared/core/infrastructure": "tests/core/infrastructure",
    "libs/shared/rs_shared/core/services": "tests/core/services",
    "libs/shared/rs_shared/models": "tests/models",
    "libs/shared/rs_shared/services": "tests/services",
    "libs/shared/rs_shared/templates": "tests/templates",
    "services/api/rs_api/infrastructure": "tests/api/infrastructure",
    "services/api/rs_api/api": "tests/api",
    "services/worker/rs_worker": "tests/worker",
}

# Source files that don't require tests (exceptions, simple factories, etc.)
EXCLUDED_SOURCE_FILES: set[str] = {
    # src/api/seo/ is a package whose internal modules (_jsonld, _render, etc.)
    # are exercised end-to-end by tests/api/test_seo.py — the integration tests
    # cover every path through the package via real HTTP responses. Per-module
    # unit tests would duplicate the integration coverage; the package was split
    # only to satisfy the 200-line file cap, not for test isolation.
    "services/api/rs_api/api/seo/_articles.py",
    "services/api/rs_api/api/seo/_content.py",
    "services/api/rs_api/api/seo/_jsonld.py",
    "services/api/rs_api/api/seo/_pages.py",
    "services/api/rs_api/api/seo/_render.py",
    "services/api/rs_api/api/seo/_routes.py",
    "services/api/rs_api/api/seo/_sitemap.py",
    # Two version-string constants (no logic to test).
    "libs/shared/rs_shared/services/utils/legal.py",
    # A single typing.Protocol (the candidate-provisioning DI boundary) — no
    # runtime logic. Its concrete implementation (auth.register_candidate) and
    # the injection are exercised end-to-end by tests/api/public/test_applications.py.
    "libs/shared/rs_shared/services/utils/candidate_provisioning.py",
    # Sprint 11 / #606 — helper modules split out of applications.py to
    # satisfy file-size caps. Exercised end-to-end via
    # tests/services/public/test_applications.py and
    # tests/api/public/test_applications.py respectively.
    "libs/shared/rs_shared/services/public/_application_helpers.py",
    "services/api/rs_api/api/public/_apply_handler.py",
    # HTTP upload guard (UploadFile → bytes, MIME/size checks). A thin FastAPI
    # wrapper split out of core/services/file_validation.py to keep the domain
    # framework-free; exercised end-to-end via the four upload-endpoint tests
    # (auth registration, candidate profile, candidate + public applications).
    "services/api/rs_api/api/uploads.py",
    # Sprint 11 / #609 — shared resume-streaming helper imported by both
    # the admin (src/api/company/resumes.py) and candidate-facing
    # (src/api/candidate/applications.py) resume endpoints. Exercised
    # end-to-end via the consumer endpoints' tests.
    "services/api/rs_api/api/_resume_streaming.py",
    # Helper modules split out of admin service files to satisfy the 300-line
    # file cap. Exercised end-to-end via tests/services/admin/test_candidates.py,
    # test_applications.py, and test_jobs.py respectively.
    "libs/shared/rs_shared/services/admin/_candidates_purge.py",
    "libs/shared/rs_shared/services/admin/_application_status.py",
    "libs/shared/rs_shared/services/admin/_job_close.py",
    # Split out of overview.py and candidates.py for the 300-line cap; exercised
    # end-to-end via tests/services/admin/test_overview.py and test_candidates.py.
    "libs/shared/rs_shared/services/admin/_overview_scalars.py",
    "libs/shared/rs_shared/services/admin/_candidate_reads.py",
    # Helper modules split out of src/services/company/jobs.py to satisfy the
    # 300-line file cap. Exercised end-to-end via tests/services/company/test_jobs.py.
    "libs/shared/rs_shared/services/company/_jobs_applications.py",
    "libs/shared/rs_shared/services/company/_jobs_recommendations.py",
    # OTel SDK initialisation — thin wrappers around TracerProvider,
    # MeterProvider, and LoggerProvider. No domain logic; exercised
    # end-to-end by every request/task that emits telemetry in prod.
    "libs/shared/rs_shared/core/infrastructure/telemetry.py",
    # SQLModel table declarations with no functions. A per-module test would
    # restate the declarations; they are exercised by the service tests that
    # read and write them (a model-vs-migration drift check is #1057). Remove
    # an entry here as soon as its module gains a function.
    "libs/shared/rs_shared/models/_embedding.py",
    "libs/shared/rs_shared/models/audit.py",
    "libs/shared/rs_shared/models/auth_tokens.py",
    "libs/shared/rs_shared/models/email_outbox.py",
    "libs/shared/rs_shared/models/matching.py",
    "libs/shared/rs_shared/models/quota.py",
}

# Test files allowed to exist without a matching source file.
# Use this only for cross-cutting behavioral tests that don't map to a single
# module (e.g. integration tests that span a whole package).
EXCLUDED_TEST_FILES: set[str] = {
    # Integration tests for the src/api/seo/ package — exercises all internal
    # modules via real HTTP. The package's internal _*.py files are listed in
    # EXCLUDED_SOURCE_FILES above for the same reason.
    "tests/api/test_seo.py",
    # Executes data migrations' real SQL against a seeded database. Maps to
    # alembic/versions/, which is outside SOURCE_TO_TEST_MAPPING and has no
    # per-module test convention.
    "tests/test_migrations.py",
}


def _longest_match(path: Path, roots: list[str]) -> str | None:
    """The most specific mapped root that contains ``path``, if any."""
    matches = [r for r in roots if path.is_relative_to(r)]
    return max(matches, key=len) if matches else None


def get_expected_test_file(source_file: Path) -> Path | None:
    """Get the expected test file path for a source file."""
    source_dir = _longest_match(source_file, list(SOURCE_TO_TEST_MAPPING))
    if source_dir is None:
        return None
    relative_path = source_file.relative_to(source_dir)
    test_dir = SOURCE_TO_TEST_MAPPING[source_dir]
    return Path(test_dir) / relative_path.parent / f"test_{relative_path.name}"


def get_expected_source_file(test_file: Path) -> Path | None:
    """Get the expected source file path for a test file."""
    test_to_source = {t: s for s, t in SOURCE_TO_TEST_MAPPING.items()}
    test_dir = _longest_match(test_file, list(test_to_source))
    if test_dir is None:
        return None
    relative_path = test_file.relative_to(test_dir)
    # test_X.py -> X.py
    if not relative_path.name.startswith("test_"):
        return None
    source_file_name = relative_path.name[len("test_") :]
    return Path(test_to_source[test_dir]) / relative_path.parent / source_file_name


def _files_under(dirs: list[str], pattern: str) -> list[Path]:
    """Unique files matching ``pattern`` under any of ``dirs`` (they nest)."""
    found = {f for d in dirs if Path(d).exists() for f in Path(d).rglob(pattern)}
    return sorted(found)


def check_missing_test_files() -> list[str]:
    """Find source files without a matching test file."""
    violations: list[str] = []

    for py_file in _files_under(list(SOURCE_TO_TEST_MAPPING), "*.py"):
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

    for py_file in _files_under(list(SOURCE_TO_TEST_MAPPING.values()), "test_*.py"):
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


def check_stale_exclusions() -> list[str]:
    """Find exclusion entries whose file no longer exists.

    An entry for a deleted file silently hides nothing, and its comment keeps
    claiming coverage or an exemption that is gone (a fail-closed test once
    stayed "excluded" for months after it was deleted).
    """
    return [
        f"{entry}: excluded in {name}, but the file does not exist"
        for name, entries in (
            ("EXCLUDED_SOURCE_FILES", EXCLUDED_SOURCE_FILES),
            ("EXCLUDED_TEST_FILES", EXCLUDED_TEST_FILES),
        )
        for entry in sorted(entries)
        if not Path(entry).is_file()
    ]


def main() -> None:
    missing = check_missing_test_files()
    orphans = check_orphan_test_files()
    stale = check_stale_exclusions()

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

    if stale:
        if missing or orphans:
            print()
        print("❌ Stale exclusions detected:")
        print("Remove the entry, or restore the file it names.\n")
        for v in stale:
            print(f"  {v}")

    if missing or orphans or stale:
        sys.exit(1)

    print("✅ All source files have matching test files (and vice versa)")
    sys.exit(0)


if __name__ == "__main__":
    main()
