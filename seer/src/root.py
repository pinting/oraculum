"""Unqualified field resolution.

The table space is a boolean function over one variable per table. A field
living in tables `{t1..tk}` contributes the mutual exclusion constraint "one of
these is the table this field came from, and it is not the others", and a
running product `P <- P * C(f)` accumulates the selection: `P = 0` means the
selection is contradictory, asserting a table asks whether it is still viable,
and the all-zero assignment holding asks whether the query is settled.

The algebra itself is `backend.py`'s business. What this module does depend on
is that the questions come in batches: a selection invalidates every field name
and every table at once, so `nonzero` and `viable` ask for the whole answer
rather than looping here.

Two properties the token driven engine depends on, both explained in the
README: selections report failure with a bool rather than raising, and `copy()`
gives each branch of the syntax graph its own `current` while sharing the
algebra and the constraint table, which are immutable once built.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .backend import Algebra, Poly

class Root:
    __slots__ = (
        "_algebra",
        "_tables",
        "_constraints",
        "_names",
        "_polys",
        "_current",
        "_fields",
        "_excluded_fields",
        "_used_tables",
    )

    def __init__(self, tables: Mapping[str, Sequence[str]] | None = None) -> None:
        if tables is None:
            return

        all_tables: list[str] = sorted(tables.keys())

        self._algebra: Algebra = Algebra(all_tables)
        self._tables: frozenset[str] = frozenset(all_tables)

        tables_by_field: dict[str, set[str]] = {}

        for table, fields in tables.items():
            for name in fields:
                tables_by_field.setdefault(name, set()).add(table)

        self._constraints: dict[str, Poly] = {
            name: self._algebra.mutual_exclusion(sorted(field_tables))
            for name, field_tables in tables_by_field.items()
        }

        # The constraint table in the order `nonzero` answers in, kept rather
        # than rebuilt per refresh.
        self._names: tuple[str, ...] = tuple(self._constraints)
        self._polys: tuple[Poly, ...] = tuple(self._constraints.values())

        self._current: Poly = self._algebra.one()
        self._fields: frozenset[str] = frozenset()
        self._excluded_fields: frozenset[str] = frozenset()
        self._used_tables: frozenset[str] = frozenset()

        self._refresh_fields()

    def copy(self) -> "Root":
        """Clone of the resolver state.

        The algebra, its variables and the constraints never change after
        construction, so a clone shares them; the running function is a value,
        so `current` needs no copying either.
        """

        clone: Root = Root.__new__(Root)

        clone._algebra = self._algebra
        clone._tables = self._tables
        clone._constraints = self._constraints
        clone._names = self._names
        clone._polys = self._polys
        clone._current = self._current
        clone._fields = self._fields
        clone._excluded_fields = self._excluded_fields
        clone._used_tables = self._used_tables

        return clone

    def _refresh_fields(self) -> None:
        """Split the field names by whether they still have a product."""

        surviving: Sequence[bool] = self._algebra.nonzero(self._current, self._polys)

        self._fields = frozenset(
            name for name, alive in zip(self._names, surviving) if alive
        )
        self._excluded_fields = frozenset(
            name for name, alive in zip(self._names, surviving) if not alive
        )

    def get_fields(self) -> frozenset[str]:
        return self._fields

    def use_field(self, field: str) -> bool:
        """Multiply the running product by this field's constraint."""

        constraint: Poly | None = self._constraints.get(field)

        if constraint is None:
            return False

        next_current: Poly = self._algebra.product(self._current, constraint)

        if self._algebra.is_zero(next_current):
            return False

        self._current = next_current

        self._refresh_fields()

        return True

    def use_table(self, name: str) -> bool:
        """Assert the table is in the FROM clause."""

        if name not in self._tables:
            return False

        next_current: Poly = self._algebra.assume(self._current, name)

        if self._algebra.is_zero(next_current):
            return False

        self._current = next_current
        self._used_tables = self._used_tables | {name}

        self._refresh_fields()

        return True

    def get_used_tables(self) -> frozenset[str]:
        return self._used_tables

    def get_required_tables(self) -> frozenset[str]:
        """Tables the running product still depends on and can satisfy."""

        if self.is_satisfied():
            return frozenset()

        return self._algebra.constrained(self._current) & self._algebra.viable(self._current)

    def get_excluded_tables(self) -> frozenset[str]:
        """Tables already used plus those that would collapse the product."""

        return self._used_tables | (self._tables - self._algebra.viable(self._current))

    def get_excluded_fields(self) -> frozenset[str]:
        return self._excluded_fields

    def is_satisfied(self) -> bool:
        """True once the product holds with every table variable at zero."""

        return self._algebra.holds_empty(self._current)

    def __str__(self) -> str:
        """The running product, simplified to disjunctive normal form."""

        return self._algebra.render(self._current)

    def __repr__(self) -> str:
        return f"Root({self})"
