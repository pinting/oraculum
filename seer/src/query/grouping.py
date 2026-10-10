"""GROUP BY: the columns a query groups on, and what they cover.

Grouping is written against the closed relation, like a filter, so a key is an
`Operand` and two spellings of one column are one key: `GROUP BY u.email` and
`GROUP BY email` say the same thing where one node supplies `email`, and the
second is refused once the first is in.

What grouping decides is which plain columns the projection may keep. Once any
item aggregates, every item that does not has to be a grouped column, because
anything else has no single value per group. `covers` is that test, asked of
the projection's plain items as the relation resolves them.

A grouping is a value; adding a key answers with a new one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .relation import Operand

@dataclass(frozen=True)
class Grouping:
    keys: tuple[Operand, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.keys)

    def contains(self, operand: Operand) -> bool:
        """Whether `operand` is a grouped column, however it is spelled."""

        return any(key.same_column(operand) for key in self.keys)

    def add(self, key: Operand) -> "Grouping | None":
        """Group on `key` too; `None` where that column is already grouped."""

        if self.contains(key):
            return None

        return Grouping(self.keys + (key,))

    def covers(self, columns: Iterable[Operand | None]) -> bool:
        """Whether every column is grouped; one that resolved to nothing is not."""

        return all(column is not None and self.contains(column) for column in columns)

    def __str__(self) -> str:
        return ", ".join(key.text for key in self.keys)
