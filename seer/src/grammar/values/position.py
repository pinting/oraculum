"""Where a value is written, which decides what it may be."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from ...model import LITERAL_CLASSES, NUMERIC, Kinds, TypeClass
from ...query import Expr
from ...runtime import Thunk
from ..tokens import EXPRESSION_DEPTH

Then = Callable[[Expr], Thunk]

def meet(first: Kinds | None, second: Kinds | None) -> Kinds | None:
    """The classes both allow; `None` allows every class."""

    if first is None:
        return second

    if second is None:
        return first

    return first & second

@dataclass(frozen=True)
class Position:
    """Where a value is written, which decides what it may be."""

    kinds: Kinds | None = None
    """The classes the value may have; `None` for every class."""

    depth: int = EXPRESSION_DEPTH
    """How many calls and CASEs may still nest."""

    aggregates: bool = True
    windows: bool = True

    def allows(self, kind: TypeClass) -> bool:
        return self.kinds is None or kind in self.kinds

    def classes(self) -> tuple[TypeClass, ...]:
        """The classes with a literal the value may have, in a stable order."""

        return tuple(kind for kind in LITERAL_CLASSES if self.allows(kind))

    def within(self, kinds: Kinds | None, aggregates: bool | None = None) -> "Position":
        """An argument of a call, or a part of a CASE, written here."""

        return Position(
            kinds,
            self.depth - 1,
            self.aggregates if aggregates is None else aggregates,
            windows=False,
        )

    def beside(self) -> "Position":
        """The right side of an arithmetic operator written here."""

        return replace(self, kinds=NUMERIC)
