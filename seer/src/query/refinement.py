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

from ..model import TypeClass
from .expression import Expr
from .grouping import Grouping
from .projection import Projection
from .operand import Operand
from .relation import Relation

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

    def group_candidates(self) -> tuple[Operand, ...]:
        """Columns that may be grouped on next: every one not grouped yet."""

        return tuple(operand for operand in self.operands() if not self.grouping.contains(operand))

    def grouped(self, kind: TypeClass | None = None) -> tuple[Operand, ...]:
        """Every grouped value: each spelling of a grouped column, and each computed key.

        These are what may be written as a whole wherever only grouped values
        may stand - HAVING, and the ORDER BY of a grouped query.
        """

        columns: tuple[Operand, ...] = tuple(
            operand for operand in self.operands(kind) if self.grouping.contains(operand)
        )
        computed: tuple[Operand, ...] = tuple(
            key for key in self.grouping.keys
            if not key.is_column and (kind is None or key.kind is kind)
        )

        return columns + computed

    def key(self, expr: Expr) -> str:
        """The key an expression of the projection has in this relation."""

        return expr.render(self.relation.key)

    def is_aggregated(self, projection: Projection) -> bool:
        """Whether the query folds groups: it groups, or it aggregates without grouping."""

        return bool(self.grouping) or projection.has_aggregates()

    def covers(self, projection: Projection) -> bool:
        """Whether every item is single valued, which is only a question once the query aggregates."""

        if not self.is_aggregated(projection):
            return True

        return all(self.grouping.covers(item.expr, self.key) for item in projection.items)

    # -- writing it -------------------------------------------------------

    def filter(self, text: str) -> "Refinement":
        return replace(self, where=self.where + (text,))

    def group(self, key: Operand) -> "Refinement | None":
        grouped: Grouping | None = self.grouping.add(key)

        return None if grouped is None else replace(self, grouping=grouped)

    def having_filter(self, text: str) -> "Refinement":
        return replace(self, having=self.having + (text,))

    def __str__(self) -> str:
        return (
            f"Used filters     = {', '.join(self.where)}\n"
            f"Grouped by       = {self.grouping}\n"
            f"Having           = {', '.join(self.having)}"
        )
