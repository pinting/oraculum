"""Unqualified field resolution.

The table space is a boolean function over one variable per table. A field
living in tables `{t1..tk}` contributes the mutual exclusion constraint "one of
these is the table this field came from, and it is not the others", and a
running product `P <- P * C(f)` accumulates the selection: `P = 0` means the
selection is contradictory, asserting a table asks whether it is still viable,
and the all-zero assignment holding asks whether the query is settled.

A field handed to a function is constrained harder. `SUM(id)` says that the
table supplying `id` has a numeric `id`, so of the owners `T(f)` only the ones
whose column is of an accepted class `K` may be it - and the others may not be
in the clause at all, or the bare name would be ambiguous between them:

    C_K(f) = C(T_K(f)) * prod_{t in T(f) - T_K(f)} (1 + t)

which is `C(f)` itself when every owner qualifies. One constraint table is
built per class set the functions ask for, all of them up front.

The algebra itself is the kernel's business, through `runtime.backend`. What
this module does depend on is that the questions come in batches: a selection
invalidates every field name and every table at once, so `nonzero` and
`viable` ask for the whole answer rather than looping here.

Two properties the token driven engine depends on, both explained in the
README: selections report failure with a bool rather than raising, and `copy()`
gives each branch of the syntax graph its own `current` while sharing the
algebra and the constraint tables, which are immutable once built.
"""

from __future__ import annotations

from typing import Iterable, NamedTuple, Sequence

from ..runtime import Algebra, Poly
from .columns import ColumnIndex, Kinds

class Constraints(NamedTuple):
    """One constraint per field name, in the order `nonzero` answers in."""

    names: tuple[str, ...]
    polys: tuple[Poly, ...]
    by_name: dict[str, Poly]

def _constraints(algebra: Algebra, index: ColumnIndex, kinds: Kinds | None) -> Constraints:
    by_name: dict[str, Poly] = {}

    for name, owners in index:
        accepted: frozenset[str] = index.owners(name, kinds)

        if not accepted:
            continue

        poly: Poly = algebra.mutual_exclusion(sorted(accepted))

        for table in sorted(owners - accepted):
            absent: Poly = algebra.sum(algebra.one(), algebra.mutual_exclusion([table]))
            poly = algebra.product(poly, absent)

        by_name[name] = poly

    return Constraints(tuple(by_name), tuple(by_name.values()), by_name)

class Root:
    __slots__ = (
        "_algebra",
        "_tables",
        "_constraints",
        "_current",
        "_fields",
        "_excluded_fields",
        "_used_tables",
    )

    def __init__(self, index: ColumnIndex | None = None, kinds: Iterable[Kinds] = ()) -> None:
        if index is None:
            return

        self._algebra: Algebra = Algebra(sorted(index.tables))
        self._tables: frozenset[str] = index.tables

        self._constraints: dict[Kinds | None, Constraints] = {
            restriction: _constraints(self._algebra, index, restriction)
            for restriction in (None, *kinds)
        }

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
        clone._current = self._current
        clone._fields = self._fields
        clone._excluded_fields = self._excluded_fields
        clone._used_tables = self._used_tables

        return clone

    def _surviving(self, kinds: Kinds | None) -> tuple[frozenset[str], frozenset[str]]:
        """The field names that still have a product, and the ones that do not."""

        table: Constraints = self._constraints[kinds]
        alive: Sequence[bool] = self._algebra.nonzero(self._current, table.polys)

        return (
            frozenset(name for name, ok in zip(table.names, alive) if ok),
            frozenset(name for name, ok in zip(table.names, alive) if not ok),
        )

    def _refresh_fields(self) -> None:
        self._fields, self._excluded_fields = self._surviving(None)

    def get_fields(self, kinds: Kinds | None = None) -> frozenset[str]:
        """Fields still selectable, optionally as an argument restricted to `kinds`."""

        if kinds is None:
            return self._fields

        return self._surviving(kinds)[0]

    def use_field(self, field: str, kinds: Kinds | None = None) -> bool:
        """Multiply the running product by this field's constraint."""

        constraint: Poly | None = self._constraints[kinds].by_name.get(field)

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
