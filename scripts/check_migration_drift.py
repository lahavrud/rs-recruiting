#!/usr/bin/env python3
"""Fail when the migrated database and the SQLModel models disagree.

Dev and tests build the schema with ``SQLModel.metadata.create_all``; prod
builds it by running the Alembic chain. This compares the two: run it against
a database that ``alembic upgrade head`` built from empty (CI does, see the
"Migration chain" step in ci.yml), and it reports every difference Alembic's
autogenerate can see (tables, columns, types, nullability, indexes, FKs).

A difference means one side changed without the other: a model edit with no
migration, or a migration the model doesn't reflect. Fix it by adding the
missing migration, or by updating the model to match what the chain (and
therefore prod) has. Only a difference that is deliberate goes in
KNOWN_DRIFT, with the reason.

Not compared: server defaults (too noisy between SQLModel and reflection),
triggers and functions (tests/test_migrations.py checks the one trigger).

Usage: DATABASE_URL=<migrated db> uv run python scripts/check_migration_drift.py
"""

import asyncio
import sys
from typing import Any

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

import rs_shared.models  # noqa: F401  (registers every table on SQLModel.metadata)
from rs_shared.core.infrastructure.config import settings

# "<kind>:<table>[.<column or index>]" -> why this difference is accepted.
KNOWN_DRIFT: dict[str, str] = {
    # The old per-account lockout columns (replaced by login_throttle, #1185)
    # are unmapped one release before they are dropped, because the deploy
    # migrates before it rolls: old tasks still select them. Remove both
    # entries with the migration that drops the columns (#1186).
    "remove_column:user.failed_login_attempts": "unmapped ahead of the drop (#1186)",
    "remove_column:user.locked_until": "unmapped ahead of the drop (#1186)",
}


def _include_object(
    obj: Any, name: str, type_: str, reflected: bool, compare_to: Any
) -> bool:
    return not (type_ == "table" and name == "alembic_version")


def _key(diff: tuple) -> str:
    """A stable identifier for one diff, used for KNOWN_DRIFT and output."""
    kind = diff[0]
    if kind in ("add_table", "remove_table"):
        return f"{kind}:{diff[1].name}"
    if kind in ("add_column", "remove_column"):
        return f"{kind}:{diff[2]}.{diff[3].name}"
    if kind in ("add_index", "remove_index"):
        return f"{kind}:{diff[1].table.name}.{diff[1].name}"
    if kind in ("add_constraint", "remove_constraint"):
        return f"{kind}:{diff[1].table.name}.{diff[1].name}"
    if kind in ("add_fk", "remove_fk"):
        return f"{kind}:{diff[1].parent.name}.{diff[1].name}"
    if kind.startswith("modify_"):
        return f"{kind}:{diff[2]}.{diff[3]}"
    return f"{kind}:{diff!r}"


def _describe(diff: tuple) -> str:
    kind = diff[0]
    if kind.startswith("modify_"):
        _, _schema, _table, _column, _info, old, new = diff
        return f"database has {old!r}, model has {new!r}"
    return ""


def _flatten(diffs: list) -> list[tuple]:
    """Column modifications come back grouped in a list; flatten them."""
    flat: list[tuple] = []
    for diff in diffs:
        if isinstance(diff, list):
            flat.extend(diff)
        else:
            flat.append(diff)
    return flat


def _compare(connection: Connection) -> list[tuple]:
    context = MigrationContext.configure(
        connection,
        opts={"compare_type": True, "include_object": _include_object},
    )
    return _flatten(compare_metadata(context, SQLModel.metadata))


async def _diffs() -> list[tuple]:
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_compare)
    finally:
        await engine.dispose()


def main() -> None:
    diffs = asyncio.run(_diffs())
    unexpected = [d for d in diffs if _key(d) not in KNOWN_DRIFT]
    accepted = [d for d in diffs if _key(d) in KNOWN_DRIFT]

    for diff in accepted:
        print(f"accepted  {_key(diff)}: {KNOWN_DRIFT[_key(diff)]}")
    stale = set(KNOWN_DRIFT) - {_key(d) for d in diffs}
    for key in sorted(stale):
        print(f"stale KNOWN_DRIFT entry (no longer differs, remove it): {key}")

    if unexpected:
        print("❌ The migrated schema and the models disagree:\n")
        for diff in unexpected:
            detail = _describe(diff)
            print(f"  {_key(diff)}" + (f"  ({detail})" if detail else ""))
        print(
            "\nAdd the missing migration, or update the model to match the "
            "chain. See .claude/rules/migrations.md."
        )
    if unexpected or stale:
        sys.exit(1)

    print("✅ Migrated schema matches the models")


if __name__ == "__main__":
    main()
