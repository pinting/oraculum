"""The projection: what a query has selected, item by item.

An item is an expression (`expression.py`), optionally named by `AS`. The
projection records the items in order and answers the questions the later
clauses ask about them:

* which names it outputs, which is what a derived table's columns are called
  and what an ORDER BY may refer to;
* which columns it names bare, which no two FROM nodes may then both supply;
* whether it aggregates, which decides whether the rest of it has to be
  grouped.

It also holds the one piece of state that spans two tokens: the qualifier an
`<alias>.` opens, which the column after the dot consumes.

A projection is a value. Every operation answers with a new one, so a branch
that copies its query shares the projection until it selects something.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace

from .expression import Column, Expr

@dataclass(frozen=True)
class Item:
    expr: Expr

    alias: str | None = None
    """The name `AS` gave the item."""

    @property
    def output(self) -> str | None:
        """The name the item's column goes by in the result, if it has one.

        A column keeps its own; anything computed has only the one `AS` gives
        it - what SQL would call it otherwise is every dialect's own guess.
        """

        if self.alias is not None:
            return self.alias

        return self.expr.name if isinstance(self.expr, Column) else None

    def __str__(self) -> str:
        return str(self.expr) if self.alias is None else f"{self.expr} AS {self.alias}"

@dataclass(frozen=True)
class Projection:
    items: tuple[Item, ...] = ()

    qualifier: str = ""
    """The alias an `<alias>.` has opened, until the next column consumes it."""

    distinct: bool = False
    """Whether the projection was written `SELECT DISTINCT`."""

    def open(self, qualifier: str) -> "Projection":
        return replace(self, qualifier=qualifier)

    def consume(self) -> "Projection":
        """Close the qualifier, which the column just written has taken."""

        return replace(self, qualifier="")

    def deduplicate(self) -> "Projection":
        return replace(self, distinct=True)

    def add(self, expr: Expr) -> "Projection":
        return replace(self, items=self.items + (Item(expr),))

    def name_last(self, alias: str) -> "Projection | None":
        """Name the item just written; `None` where it is named already."""

        if not self.items or self.items[-1].alias is not None:
            return None

        return replace(self, items=self.items[:-1] + (replace(self.items[-1], alias=alias),))

    @property
    def last(self) -> Item | None:
        return self.items[-1] if self.items else None

    def outputs(self) -> tuple[str, ...]:
        """The output names of the items that have one, in order."""

        return tuple(item.output for item in self.items if item.output is not None)

    def unique_outputs(self) -> frozenset[str]:
        """The output names exactly one item goes by, which is what a name may refer to."""

        counts: Counter[str] = Counter(name.lower() for name in self.outputs())

        return frozenset(name for name in self.outputs() if counts[name.lower()] == 1)

    def aliases(self) -> frozenset[str]:
        """The names `AS` introduced."""

        return frozenset(item.alias for item in self.items if item.alias is not None)

    def has_aggregates(self) -> bool:
        return any(item.expr.aggregates() for item in self.items)

    def bare_columns(self) -> frozenset[str]:
        """Every column the projection names without a qualifier, however deep."""

        return frozenset(
            column.name
            for item in self.items
            for column in item.expr.columns()
            if not column.qualifier
        )

    def __str__(self) -> str:
        text: str = ", ".join(str(item) for item in self.items)

        return f"DISTINCT {text}" if self.distinct else text
