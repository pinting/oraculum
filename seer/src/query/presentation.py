"""ORDER BY and LIMIT: how a complete result is presented.

Both are written once the body of the query is complete - its FROM clause
placed, its grouping covering its items - and they no longer change what the
result holds, only its order and how much of it is returned. They share one
part, built when the body is left.

What an ORDER BY may sort by depends on what the result is:

* an **output name** is always on offer, for every name exactly one item goes
  by - a name two items share would be ambiguous, and SQL refuses it;
* over a **plain** query, any value of the relation as well, columns and
  scalar functions over them;
* over an **aggregated** one only single valued ones: grouped values,
  functions over them, and aggregates;
* over a `SELECT DISTINCT` or a **compound** query, output names alone. Once
  rows have been deduplicated or combined, nothing but the result's own
  columns is left to sort by.

The part holds what is on offer as two sets - the outputs, which are written
by name and only as a whole, and the leaves a function may be applied to - and
the virtual table decides which mode fills them. A value sorted by once is not
offered again, however it is spelled.

LIMIT and OFFSET take a count each, OFFSET only after LIMIT.

The part is a value; every operation answers with a new one.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import Callable

from ..model import Kinds
from .derivation import Result
from .expression import Direction
from .projection import Projection
from .refinement import Refinement
from .operand import Operand

@dataclass(frozen=True)
class Presentation:
    outputs: tuple[Operand, ...] = ()
    """The result columns, by name."""

    leaves: tuple[Operand, ...] = ()
    """The values of the relation that may be sorted by, and that functions may be applied to."""

    aggregates: bool = False
    """Whether an aggregate may be sorted by."""

    order: tuple[tuple[Operand, Direction], ...] = ()
    limit: str | None = None
    offset: str | None = None

    def _is_ordered(self, operand: Operand) -> bool:
        return any(key.same_value(operand) for key, _ in self.order)

    def candidates(self, kinds: Kinds | None = None) -> tuple[Operand, ...]:
        """What may be sorted by as a whole: outputs first, then leaves they do not spell."""

        spelled: frozenset[str] = frozenset(output.text.lower() for output in self.outputs)
        leaves: tuple[Operand, ...] = tuple(
            leaf for leaf in self.leaves if leaf.text.lower() not in spelled
        )

        return tuple(
            operand
            for operand in self.outputs + leaves
            if not self._is_ordered(operand) and (kinds is None or operand.kind in kinds)
        )

    def is_exhausted(self) -> bool:
        """Whether nothing is left to sort by."""

        return not (self.candidates() or self.leaves or self.aggregates)

    def arguments(self) -> tuple[Operand, ...]:
        """What a function sorted by may be applied to."""

        return self.leaves

    def sort(self, operand: Operand) -> "Presentation | None":
        if (operand.is_column or operand in self.outputs) and self._is_ordered(operand):
            return None

        return replace(self, order=self.order + ((operand, ""),))

    def direct(self, direction: Direction) -> "Presentation | None":
        """Give the key just written its direction."""

        if not self.order or self.order[-1][1]:
            return None

        key, _ = self.order[-1]

        return replace(self, order=self.order[:-1] + ((key, direction),))

    def limited(self, count: str) -> "Presentation | None":
        return None if self.limit is not None else replace(self, limit=count)

    def offset_by(self, count: str) -> "Presentation | None":
        if self.limit is None or self.offset is not None:
            return None

        return replace(self, offset=count)

    @classmethod
    def of_compound(cls, result: Result) -> "Presentation":
        """What a compound's result may be sorted by: its output names, as the first member gave them."""

        return cls(outputs(result, lambda _, name: f"#{name}"))

    @classmethod
    def of_query(cls, projection: Projection, result: Result, refinement: Refinement) -> "Presentation":
        """What one query's result may be sorted by, which depends on what the result is."""

        items = projection.items
        named: tuple[Operand, ...] = outputs(result, lambda position, _: refinement.key(items[position].expr))

        if projection.distinct:
            return cls(named)

        if refinement.is_aggregated(projection):
            return cls(named, refinement.grouped(), aggregates=True)

        return cls(named, refinement.operands())

    def __str__(self) -> str:
        order: str = ", ".join(f"{key} {direction}".rstrip() for key, direction in self.order)

        return (
            f"Ordered by       = {order}\n"
            f"Limit            = {self.limit or ''}{' OFFSET ' + self.offset if self.offset else ''}"
        )

def outputs(result: Result, key: Callable[[int, str], str]) -> tuple[Operand, ...]:
    """The columns of `result` an ORDER BY may name: those exactly one goes by.

    `key` gives each the key it shares with whatever else spells its value.
    """

    counts: Counter[str] = Counter(output.name.lower() for output in result if output.name)

    return tuple(
        Operand("", output.name, output.name, output.field, key(position, output.name))
        for position, output in enumerate(result)
        if output.name and counts[output.name.lower()] == 1
    )

def can_sort(projection: Projection, compound: Result | None) -> bool:
    """Whether a result has anything to sort by.

    One that may only be sorted by its output names - deduplicated, or
    compound - has nothing where none of them is unique.
    """

    if compound is not None:
        return bool(outputs(compound, lambda _, name: name))

    return not projection.distinct or bool(projection.unique_outputs())
