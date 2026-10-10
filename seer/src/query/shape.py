"""Shape: what a projection has to produce, where something outside it decides.

Usually nothing does, and a query selects as many items of whatever classes it
likes. Two things take that freedom away:

* a definition with a column list, `WITH t(a, b) AS (...)`, has to produce
  exactly as many columns as the list names;
* a later member of a compound, `... UNION SELECT ...`, has to produce the
  columns the first member did - as many, and each of the class it had.

A shape is the arity and, per position, the classes allowed there.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..model import Kinds, classify
from .derivation import Result

@dataclass(frozen=True)
class Shape:
    kinds: tuple[Kinds | None, ...]

    @classmethod
    def arity(cls, count: int) -> "Shape":
        """Any `count` columns."""

        return cls((None,) * count)

    @classmethod
    def of(cls, result: Result) -> "Shape":
        """Columns of the classes `result`'s have."""

        return cls(tuple(frozenset({classify(output.field.type)}) for output in result))

    def __len__(self) -> int:
        return len(self.kinds)

    def at(self, position: int) -> Kinds | None:
        return self.kinds[position]
