"""Which tables carry each column name.

Both resolvers ask the same question of the schema - where can a field named
`f` come from - and differ only in what they do with the answer: `Root` turns
it into a polynomial, `Scope` intersects with it. So the answer is computed
once, here, and shared by every copy of both.

A name is owned per type class as well, because a function argument does not
accept every column of a name: `SUM(id)` may only be supplied by a table whose
`id` is numeric. `owners(field, kinds)` is that narrower question; leaving
`kinds` out asks the plain one.
"""

from __future__ import annotations

from typing import Iterator

from ..model import Kinds, Schema, TypeClass, classify

class ColumnIndex:
    __slots__ = ("_tables", "_owners", "_classes")

    def __init__(self, schema: Schema) -> None:
        owners: dict[str, set[str]] = {}
        classes: dict[tuple[str, str], TypeClass] = {}

        for table, definition in schema.tables.items():
            for name, column in definition.fields.items():
                owners.setdefault(name, set()).add(table)
                classes[(table, name)] = classify(column.type)

        self._tables: frozenset[str] = frozenset(schema.tables)
        self._owners: dict[str, frozenset[str]] = {
            name: frozenset(tables) for name, tables in owners.items()
        }
        self._classes: dict[tuple[str, str], TypeClass] = classes

    @property
    def tables(self) -> frozenset[str]:
        return self._tables

    def fields(self, kinds: Kinds | None = None) -> frozenset[str]:
        """Every column name, whichever table it is on - and of one of `kinds`."""

        if kinds is None:
            return frozenset(self._owners)

        return frozenset(name for name in self._owners if self.owners(name, kinds))

    def __iter__(self) -> Iterator[tuple[str, frozenset[str]]]:
        """`(field, owners)` for every column name, in a stable order."""

        for name in sorted(self._owners):
            yield name, self._owners[name]

    def owners(self, field: str, kinds: Kinds | None = None) -> frozenset[str]:
        """The tables a column named `field` lives on, optionally of one of `kinds`."""

        tables: frozenset[str] = self._owners.get(field, frozenset())

        if kinds is None:
            return tables

        return frozenset(
            table for table in tables if self._classes[(table, field)] in kinds
        )
