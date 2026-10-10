"""Where a value is written, which decides what it may be."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
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

class Need(Enum):
    """What a value has to be made of, beyond its class."""

    ROW = "row"
    """Anything of the row: columns, and whatever is built from them."""

    CONSTANT = "constant"
    """Nothing of the row, outside an aggregate: the same value for every row."""

    AGGREGATE = "aggregate"
    """A constant that aggregates somewhere, which is what keeps a query to one row."""

@dataclass(frozen=True)
class Position:
    """Where a value is written, which decides what it may be."""

    kinds: Kinds | None = None
    """The classes the value may have; `None` for every class."""

    depth: int = EXPRESSION_DEPTH
    """How many calls and CASEs may still nest."""

    aggregates: bool = True
    windows: bool = True

    need: Need = Need.ROW

    @property
    def reads_row(self) -> bool:
        return self.need is Need.ROW

    def allows(self, kind: TypeClass) -> bool:
        return self.kinds is None or kind in self.kinds

    def classes(self) -> tuple[TypeClass, ...]:
        """The classes with a literal the value may have, in a stable order."""

        return tuple(kind for kind in LITERAL_CLASSES if self.allows(kind))

    def within(self, kinds: Kinds | None, aggregates: bool | None = None) -> "Position":
        """An argument of a call, or a part of a CASE, written here.

        It reads the row where this one does, and is constant otherwise - the
        aggregate a position needs is carried by one argument only.
        """

        return Position(
            kinds,
            self.depth - 1,
            self.aggregates if aggregates is None else aggregates,
            windows=False,
            need=Need.ROW if self.reads_row else Need.CONSTANT,
        )

    def carrying(self, kinds: Kinds | None) -> "Position":
        """The argument of a call that carries what this position needs."""

        return replace(self.within(kinds), need=self.need)

    def beside(self) -> "Position":
        """The right side of an arithmetic operator written here.

        The left side already holds whatever aggregate was needed.
        """

        need: Need = Need.ROW if self.reads_row else Need.CONSTANT

        return replace(self, kinds=NUMERIC, need=need)
