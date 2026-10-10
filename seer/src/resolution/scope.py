"""Aliased field resolution.

An alias refers to exactly one table, so unlike `root.py` there is no
cross-talk to model: plain set intersection narrows the candidates as fields
are selected. A field handed to a function intersects with the owners whose
column is of an accepted class, which is the whole of typing here. As in
`root.py`, failures are reported with a bool rather than raised, because
selections are applied speculatively during expansion.
"""

from __future__ import annotations

from .columns import ColumnIndex, Kinds

class Scope:
    __slots__ = ("_index", "_candidates", "_fields")

    def __init__(self, index: ColumnIndex | None = None) -> None:
        if index is None:
            return

        self._index: ColumnIndex = index
        self._candidates: frozenset[str] = index.tables

        self._refresh_fields()

    def copy(self) -> "Scope":
        clone: Scope = Scope.__new__(Scope)

        clone._index = self._index
        clone._candidates = self._candidates
        clone._fields = self._fields

        return clone

    def _refresh_fields(self) -> None:
        self._fields: frozenset[str] = frozenset(
            name for name, owners in self._index if owners & self._candidates
        )

    def get_fields(self, kinds: Kinds | None = None) -> frozenset[str]:
        if kinds is None:
            return self._fields

        return frozenset(
            name for name in self._fields if self._index.owners(name, kinds) & self._candidates
        )

    def use_field(self, field: str, kinds: Kinds | None = None) -> bool:
        next_candidates: frozenset[str] = self._candidates & self._index.owners(field, kinds)

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
        return self._index.tables - self._candidates

    def get_excluded_fields(self) -> frozenset[str]:
        return self._index.fields() - self._fields

    def is_satisfied(self) -> bool:
        return len(self._candidates) == 0

    def __str__(self) -> str:
        if not self._candidates:
            return "1"

        return " ^ ".join(sorted(self._candidates))

    def __repr__(self) -> str:
        return f"Scope({self})"
