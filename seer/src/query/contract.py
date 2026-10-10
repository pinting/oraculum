"""Contract: what a projection owes the place its query stands in.

The frame of a query (`frame.py`) says where it stands; the contract is what
that means for the items it may select, as three rules over the projection:

* **named** - the body of a definition exports its items as the columns of a
  table, so every item needs a name and no two may share one. An item that
  has none, or whose column's name another item goes by, may only be added
  with an `AS`;
* **shaped** - a definition with a column list, or a later member of a
  compound, has to produce a fixed number of items, each of a fixed class
  (`shape.py`);
* **simple** - a recursive member may not aggregate, window or deduplicate,
  and the definition it reads may be placed **once** at most.

A subquery adds its own (`purpose.py`):

* **single row** - a scalar subquery has to aggregate the whole of what it
  reads, so every item is an aggregate expression and nothing is grouped;
* **required** - a derived table has to export the columns the projection
  around it already read off its alias, each of the classes it read it as.
  Those are column names, which no alias may spell, so each is a column item
  of that name - and a column of that name that could not be of the class
  is offered only with an `AS`;
* **forbidden** - nor may it export a name the projection around it uses
  bare, which would make that name ambiguous: a column of that name is
  offered only with an `AS` too.

**derivable** says whether a derived table may still be opened in the query's
own FROM clause, which only the nesting limit takes away.

A contract is a value and reads the projection it is handed, so the selection
asks it and nothing else has to know which rules a frame implies.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..model import Kinds
from .expression import Expr
from .projection import Item, Projection
from .shape import Shape

@dataclass(frozen=True)
class Contract:
    named: bool = False
    shape: Shape | None = None
    simple: bool = False

    once: frozenset[str] = frozenset()
    """The tables the FROM clause may place one node of at most."""

    single_row: bool = False

    required: tuple[tuple[str, Kinds | None], ...] = ()
    """The columns the result has to export, by name, with the classes each may have."""

    forbidden: frozenset[str] = frozenset()
    """The names the result may not export."""

    derivable: bool = True

    def requirement(self, name: str | None) -> tuple[bool, Kinds | None]:
        """Whether `name` is required, and of which classes."""

        for required, kinds in self.required:
            if required == name:
                return True, kinds

        return False, None

    def kinds_at(self, position: int) -> Kinds | None:
        """The classes the item at `position` may have, where the shape fixes them."""

        if self.shape is None or position >= len(self.shape):
            return None

        return self.shape.at(position)

    def has_room(self, projection: Projection, more: int = 0) -> bool:
        """Whether `more` items beyond the next one still fit."""

        return self.shape is None or len(projection.items) + more < len(self.shape)

    def admits(self, projection: Projection, expr: Expr) -> bool:
        """Whether `expr` may be added as the next item."""

        if not self.has_room(projection):
            return False

        if self.single_row and not expr.aggregates():
            return False

        return not (self.simple and (expr.aggregates() or expr.windows()))

    def needs_name(self, projection: Projection, expr: Expr) -> bool:
        """Whether `expr` may only be added with an `AS`, as far as names alone decide.

        Whether a required column can be of its classes is the algebra's
        question, which the selection asks on top of this.
        """

        if not self.named:
            return False

        output: str | None = Item(expr).output

        return output is None or output in projection.outputs() or output in self.forbidden

    def may_end_with(self, projection: Projection, output: str | None) -> bool:
        """Whether the item being written, going by `output`, may be the last."""

        if self.shape is not None and len(projection.items) + 1 != len(self.shape):
            return False

        outputs: set[str | None] = set(projection.outputs()) | {output}

        return all(name in outputs for name, _ in self.required)

    def is_met(self, projection: Projection) -> bool:
        """Whether the projection, as it stands, is all its frame asked for."""

        if self.shape is not None and len(projection.items) != len(self.shape):
            return False

        if any(name not in projection.outputs() for name, _ in self.required):
            return False

        if not self.named:
            return True

        outputs: tuple[str, ...] = projection.outputs()

        return len(outputs) == len(projection.items) and len(set(outputs)) == len(outputs)
