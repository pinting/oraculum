"""Aliased field resolution.

An alias refers to exactly one table, so unlike `root.py` there is no
cross-talk to model: plain set intersection narrows the candidates as fields
are selected. A field handed to a function intersects with the owners whose
column is of an accepted class, which is the whole of typing here. As in
`root.py`, failures are reported with a bool rather than raised, because
selections are applied speculatively during expansion.

Where the query may still open a derived table, an alias may also turn out to
be one, `(SELECT ...) AS u`, and a derived table can export any column some
table has - `u.email` beside `u.title` is a join written inside it. So a
**derivable** alias keeps every field on offer, and its candidates may run out
without it failing: then only a derived table can be it. Whether an alias has
been placed is its own state, apart from its candidates, for that reason.
"""

from __future__ import annotations

from .columns import ColumnIndex, Kinds

class Scope:
    __slots__ = ("_index", "_derivable", "_candidates", "_fields", "_demands", "_placed")

    def __init__(self, index: ColumnIndex | None = None, derivable: bool = False) -> None:
        if index is None:
            return

        self._index: ColumnIndex = index
        self._derivable: bool = derivable
        self._candidates: frozenset[str] = index.tables
        self._placed: bool = False

        # Every field selected in the alias, with the classes it was selected
        # as - which is what a derived table standing in for the alias has to
        # export.
        self._demands: dict[str, Kinds | None] = {}

        self._refresh_fields()

    def copy(self) -> "Scope":
        clone: Scope = Scope.__new__(Scope)

        clone._index = self._index
        clone._derivable = self._derivable
        clone._candidates = self._candidates
        clone._fields = self._fields
        clone._demands = dict(self._demands)
        clone._placed = self._placed

        return clone

    def _refresh_fields(self) -> None:
        if self._placed:
            self._fields: frozenset[str] = frozenset()
        elif self._derivable:
            self._fields = self._index.fields()
        else:
            self._fields = frozenset(
                name for name, owners in self._index if owners & self._candidates
            )

    def get_fields(self, kinds: Kinds | None = None) -> frozenset[str]:
        if kinds is None:
            return self._fields

        if self._derivable and not self._placed:
            return self._index.fields(kinds)

        return frozenset(
            name for name in self._fields if self._index.owners(name, kinds) & self._candidates
        )

    def use_field(self, field: str, kinds: Kinds | None = None) -> bool:
        if self._placed:
            return False

        owners: frozenset[str] = self._index.owners(field, kinds)
        next_candidates: frozenset[str] = self._candidates & owners

        # A derived table can supply what no single table can, as long as
        # some table has the column for it to select.
        if not next_candidates and not (self._derivable and owners):
            return False

        self._candidates = next_candidates

        if field in self._demands:
            known: Kinds | None = self._demands[field]

            self._demands[field] = kinds if known is None else (known if kinds is None else known & kinds)
        else:
            self._demands[field] = kinds

        self._refresh_fields()

        return True

    def demands(self) -> dict[str, Kinds | None]:
        """The fields selected in the alias, each with the classes it has to have."""

        return dict(self._demands)

    def derive(self) -> bool:
        """Satisfy the alias with a derived table rather than one of its candidates."""

        if self._placed or not self._derivable:
            return False

        self._placed = True

        self._refresh_fields()

        return True

    def use_table(self, name: str) -> bool:
        """Pin the alias to `name`, which satisfies the scope."""

        if self._placed or name not in self._candidates:
            return False

        self._placed = True

        self._refresh_fields()

        return True

    def get_required_tables(self) -> frozenset[str]:
        """The tables the alias may still be; none once it is placed."""

        return frozenset() if self._placed else self._candidates

    def get_excluded_tables(self) -> frozenset[str]:
        return self._index.tables - self.get_required_tables()

    def get_excluded_fields(self) -> frozenset[str]:
        return self._index.fields() - self._fields

    def is_satisfied(self) -> bool:
        return self._placed

    def __str__(self) -> str:
        if self._placed:
            return "1"

        if not self._candidates:
            return "(derived)"

        return " ^ ".join(sorted(self._candidates))

    def __repr__(self) -> str:
        return f"Scope({self})"
