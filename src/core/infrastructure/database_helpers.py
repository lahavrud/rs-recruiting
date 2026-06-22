"""Async database query helpers to reduce boilerplate in service functions."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.base import ExecutableOption
from sqlmodel import SQLModel

T = TypeVar("T", bound=SQLModel)


async def get_by_id(
    session: AsyncSession,
    model: type[T],
    pk: int,
) -> T | None:
    """Fetch a single row by primary key; return None if not found."""
    result = await session.execute(
        select(model).where(model.id == pk)  # pyright: ignore[reportAttributeAccessIssue]
    )
    return result.scalar_one_or_none()


async def get_by_id_or_raise(
    session: AsyncSession,
    model: type[T],
    pk: int,
    exc_factory: Callable[[int], Exception],
    options: Sequence[ExecutableOption] | None = None,
) -> T:
    """Fetch a single row by primary key; raise exc_factory(pk) if not found.

    Args:
        session: Database session
        model: SQLModel class to query
        pk: Primary key value to look up
        exc_factory: Callable that builds the exception to raise on a miss
        options: Optional eager-loading options (e.g. ``selectinload(...)``)
            applied to the underlying select statement
    """
    stmt = select(model).where(model.id == pk)  # pyright: ignore[reportAttributeAccessIssue]
    if options:
        stmt = stmt.options(*options)
    result = await session.execute(stmt)
    obj = result.scalar_one_or_none()
    if obj is None:
        raise exc_factory(pk)
    return obj
