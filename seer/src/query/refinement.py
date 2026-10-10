"""Everything written against the closed relation: WHERE, GROUP BY, HAVING.

Once the FROM clause is closed the relation it produced is fixed, and the
clauses that follow only ever read it: a filter cannot require a table, a
grouping cannot add one. So they share one part, built when SOURCE is left,
that holds the relation and what each of them has written so far.

The part is a value. Every operation answers with a new one, so a branch that
copies its query shares it until something is written.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..model import Function, TypeClass
from .grouping import Grouping
from .projection import Projection
from .relation import Operand, Relation

@dataclass(frozen=True)
class Refinement:
    relation: Relation
    grouping: Grouping = Grouping()
    where: tuple[str, ...] = ()
    having: tuple[str, ...] = ()

    # -- what may be written ----------------------------------------------

    def operands(self, kind: TypeClass | None = None) -> tuple[Operand, ...]:
        """Columns of the relation, optionally only those of one class."""

        return self.relation.get_operands(kind)

    def aggregable(self, function: Function) -> tuple[Operand, ...]:
        """Columns of the relation `function` may be applied to."""

        return tuple(operand for operand in self.operands() if function.admits(operand.field))

    def group_candidates(self) -> tuple[Operand, ...]:
        """Columns that may be grouped on next: every one not grouped yet."""

        return tuple(operand for operand in self.operands() if not self.grouping.contains(operand))

    def grouped(self, kind: TypeClass | None = None) -> tuple[Operand, ...]:
        """Every spelling of a grouped column, optionally only of one class."""

        return tuple(operand for operand in self.operands(kind) if self.grouping.contains(operand))

    def resolve(self, projection: Projection) -> tuple[Operand | None, ...]:
        """The projection's plain items, as the relation resolves them."""

        return tuple(
            self.relation.resolve(item.reference)
            for item in projection.plain()
            if item.reference is not None
        )

    def covers(self, projection: Projection) -> bool:
        """Whether the grouping keeps every plain item a single value per group."""

        return self.grouping.covers(self.resolve(projection))

    # -- writing it -------------------------------------------------------

    def filter(self, text: str) -> "Refinement":
        return replace(self, where=self.where + (text,))

    def group(self, text: str) -> "Refinement | None":
        key: Operand | None = self.relation.resolve(text)
        grouped: Grouping | None = None if key is None else self.grouping.add(key)

        return None if grouped is None else replace(self, grouping=grouped)

    def having_filter(self, text: str) -> "Refinement":
        return replace(self, having=self.having + (text,))

    def __str__(self) -> str:
        return (
            f"Used filters     = {', '.join(self.where)}\n"
            f"Grouped by       = {self.grouping}\n"
            f"Having           = {', '.join(self.having)}"
        )
