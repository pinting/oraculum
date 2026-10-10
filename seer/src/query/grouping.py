"""GROUP BY: the values a query groups on, and what they cover.

Grouping is written against the closed relation, like a filter, so a key is an
`Operand`: a column, or a scalar function over columns. Two spellings of one
column are one key - `GROUP BY u.email` and `GROUP BY email` say the same thing
where one node supplies `email` - and a column is grouped once.

What grouping decides is which values the projection may keep. Once a query
aggregates, every item has to be single valued per group, and a value is when

* it is a grouped key itself, however it is spelled;
* it is an aggregate, which folds the group into one value;
* it is a constant - a literal, or a subquery that reads nothing of the row;
* everything it is computed from is, recursively - `LOWER(email)` over a
  grouped `email`, `COUNT(*) + 1`, `ROW_NUMBER() OVER (ORDER BY email)`.

A column that is none of these has no single value per group, and SQL refuses
it. `covers` is that test, over the projection's expressions rendered to the
keys the relation gives them.

A grouping is a value; adding a key answers with a new one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .expression import Column, Expr, Literal, Star, Subquery
from .operand import Operand

@dataclass(frozen=True)
class Grouping:
    keys: tuple[Operand, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.keys)

    def contains(self, operand: Operand) -> bool:
        """Whether `operand` is a grouped value, however it is spelled."""

        return any(key.same_value(operand) for key in self.keys)

    def add(self, key: Operand) -> "Grouping | None":
        """Group on `key` too; `None` where that column is already grouped."""

        if key.is_column and self.contains(key):
            return None

        return Grouping(self.keys + (key,))

    def covers(self, expr: Expr, key: Callable[[Expr], str]) -> bool:
        """Whether `expr` has a single value per group; `key` renders a value to its key."""

        if expr.is_aggregate or isinstance(expr, (Literal, Star, Subquery)):
            return True

        if any(grouped.key == key(expr) for grouped in self.keys):
            return True

        if isinstance(expr, Column):
            return False

        return all(self.covers(child, key) for child in expr.children())

    def __str__(self) -> str:
        return ", ".join(key.text for key in self.keys)
