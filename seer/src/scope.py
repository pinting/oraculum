"""Aliased field resolution.

An alias refers to exactly one table, so unlike `root.py` there is no
cross-talk to model: plain set intersection narrows the candidates as fields
are selected. As in `root.py`, failures are reported with a bool rather than
raised, because selections are applied speculatively during expansion.
"""

from __future__ import annotations

from typing import Mapping, Sequence

class Scope:
    __slots__ = ("_tables_by_field", "_candidates", "_tables", "_fields")

    def __init__(self, tables: Mapping[str, Sequence[str]] | None = None) -> None:
        self._tables_by_field: dict[str, frozenset[str]] = {}
        self._candidates: frozenset[str] = frozenset()
        self._tables: frozenset[str] = frozenset()
        self._fields: frozenset[str] = frozenset()

        if tables is None:
            return

        by_field: dict[str, set[str]] = {}

        for table, fields in tables.items():
            for name in fields:
                by_field.setdefault(name, set()).add(table)

        self._tables_by_field = {name: frozenset(t) for name, t in by_field.items()}
        self._candidates = frozenset(tables.keys())
        self._tables = self._candidates

        self._refresh_fields()

    def copy(self) -> "Scope":
        clone: Scope = Scope.__new__(Scope)

        clone._tables_by_field = self._tables_by_field
        clone._tables = self._tables
        clone._candidates = self._candidates
        clone._fields = self._fields

        return clone

    def _refresh_fields(self) -> None:
        self._fields = frozenset(
            name
            for name, tables in self._tables_by_field.items()
            if tables & self._candidates
        )

    def get_fields(self) -> frozenset[str]:
        return self._fields

    def use_field(self, field: str) -> bool:
        tables: frozenset[str] | None = self._tables_by_field.get(field)

        if tables is None:
            return False

        next_candidates: frozenset[str] = self._candidates & tables

        if not next_candidates:
            return False

        self._candidates = next_candidates

        self._refresh_fields()

        return True

    def use_table(self, name: str) -> bool:
        """Pin the alias to `name`, which satisfies the scope."""

        if name not in self._candidates:
            return False

        self._candidates = frozenset()

        self._refresh_fields()

        return True

    def get_required_tables(self) -> frozenset[str]:
        return self._candidates

    def get_excluded_tables(self) -> frozenset[str]:
        return self._tables - self._candidates

    def get_excluded_fields(self) -> frozenset[str]:
        return frozenset(self._tables_by_field.keys()) - self._fields

    def is_satisfied(self) -> bool:
        return len(self._candidates) == 0

    def __str__(self) -> str:
        if not self._candidates:
            return "1"

        return " ^ ".join(sorted(self._candidates))

    def __repr__(self) -> str:
        return f"Scope({self})"
