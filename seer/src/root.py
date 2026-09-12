"""Unqualified field resolution.

The table space is a Boolean polynomial ring `GF(2)[t1, ..., tn]` from
SageMath, one variable per table. A field living in tables `{t1..tk}`
contributes the mutual exclusion polynomial

    C(f) = SUM_i  t_i * PRODUCT_(j != i) (1 + t_j)

Over GF(2), `(1 + t)` is negation, so each term says "this table is on and the
others are off", and the sum admits exactly one. A running product
`P <- P * C(f)` accumulates the selection: `P = 0` means the selection is
contradictory, substituting `t = 1` asks whether a table is viable, and
evaluating with every variable at zero asks whether the query is settled.

Two properties the token driven engine depends on, both explained in the
README: selections report failure with a bool rather than raising, and `copy()`
gives each branch of the syntax graph its own `current` while sharing the ring,
the variables and the constraint table, which are immutable once built.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from sage.all import BooleanPolynomialRing
from sympy import simplify_logic
from sympy.parsing.sympy_parser import parse_expr

class Root:
    __slots__ = ("_ring", "_vars", "_constraints", "_current", "_fields", "_used_tables")

    def __init__(self, tables: Mapping[str, Sequence[str]] | None = None) -> None:
        if tables is None:
            return

        all_tables: list[str] = sorted(tables.keys())

        self._ring: Any = BooleanPolynomialRing(names=all_tables)
        self._vars: dict[str, Any] = {
            name: self._ring.gens()[i] for i, name in enumerate(all_tables)
        }

        tables_by_field: dict[str, set[str]] = {}

        for table, fields in tables.items():
            for name in fields:
                tables_by_field.setdefault(name, set()).add(table)

        self._constraints: dict[str, Any] = {
            name: self._mutual_exclusion(sorted(field_tables))
            for name, field_tables in tables_by_field.items()
        }

        self._current: Any = self._ring(1)
        self._fields: frozenset[str] = frozenset()
        self._used_tables: frozenset[str] = frozenset()

        self._refresh_fields()

    def _mutual_exclusion(self, tables: Sequence[str]) -> Any:
        """`SUM_i t_i * PRODUCT_(j != i) (1 + t_j)` -- exactly one table is on."""

        terminals: list[Any] = [self._vars[table] for table in tables]
        constraint: Any = self._ring(0)

        for i, vi in enumerate(terminals):
            term: Any = vi

            for j, vj in enumerate(terminals):
                if i != j:
                    term *= self._ring(1) + vj

            constraint += term

        return constraint

    def copy(self) -> "Root":
        """Clone of the resolver state.

        The ring, its variables and the constraint polynomials never change
        after construction, so a clone shares them; polynomials are values, so
        `current` needs no copying either.
        """

        clone: Root = Root.__new__(Root)

        clone._ring = self._ring
        clone._vars = self._vars
        clone._constraints = self._constraints
        clone._current = self._current
        clone._fields = self._fields
        clone._used_tables = self._used_tables

        return clone

    def _refresh_fields(self) -> None:
        self._fields = frozenset(
            name
            for name, constraint in self._constraints.items()
            if self._current * constraint != 0
        )

    def get_fields(self) -> frozenset[str]:
        return self._fields

    def use_field(self, field: str) -> bool:
        """Multiply the running product by this field's constraint."""

        constraint: Any | None = self._constraints.get(field)

        if constraint is None:
            return False

        next_current: Any = self._current * constraint

        if next_current == 0:
            return False

        self._current = next_current

        self._refresh_fields()

        return True

    def use_table(self, name: str) -> bool:
        """Substitute `name = 1`, asserting the table is in the FROM clause."""

        variable: Any | None = self._vars.get(name)

        if variable is None:
            return False

        next_current: Any = self._current.subs({variable: 1})

        if next_current == 0:
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

        return frozenset(
            str(variable)
            for variable in self._current.variables()
            if self._current.subs({variable: 1}) != 0
        )

    def get_excluded_tables(self) -> frozenset[str]:
        """Tables already used plus those that would collapse the product."""

        excluded: set[str] = set(self._used_tables)

        for table, variable in self._vars.items():
            if self._current.subs({variable: 1}) == 0:
                excluded.add(table)

        return frozenset(excluded)

    def get_excluded_fields(self) -> frozenset[str]:
        return frozenset(
            name
            for name, constraint in self._constraints.items()
            if self._current * constraint == 0
        )

    def is_satisfied(self) -> bool:
        """True once the product holds with every table variable at zero."""

        return self._current.subs({variable: 0 for variable in self._vars.values()}) == 1

    def __str__(self) -> str:
        """The running product, simplified to disjunctive normal form."""

        expression: str = str(self._current)

        if expression == "0":
            return "False"

        if expression == "1":
            return "True"

        expression = expression.replace("+", "^").replace("*", "&")
        expression = re.sub(r"\b1\b", "True", expression)
        expression = re.sub(r"\b0\b", "False", expression)

        return str(simplify_logic(parse_expr(expression), form="dnf"))

    def __repr__(self) -> str:
        return f"Root({self})"
