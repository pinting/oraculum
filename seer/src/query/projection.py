"""The projection: what a query has selected, item by item.

An item is a column reference, bare or qualified, or an aggregate over one -
`COUNT(*)` takes none - optionally named by `AS`. The projection records them in
order and answers the questions the later clauses ask about them:

* which names it outputs, which is what a derived table's columns are called;
* which columns it names bare, which no two FROM nodes may then both supply;
* which items are plain columns, which a GROUP BY has to cover once any item
  aggregates.

It also holds the one piece of state that spans two tokens: the qualifier an
`<alias>.` opens, which the column after the dot consumes.

A projection is a value. Every operation answers with a new one, so a branch
that copies its query shares the projection until it selects something.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..model import Function, column_name

@dataclass(frozen=True)
class Item:
    qualifier: str
    """The alias the column was written under; `""` for a bare column."""

    column: str | None
    """The column; `None` for the `*` of `COUNT(*)`."""

    function: Function | None = None
    """The aggregate the column was handed to, if any."""

    alias: str | None = None
    """The name `AS` gave the item."""

    @property
    def is_aggregate(self) -> bool:
        return self.function is not None

    @property
    def reference(self) -> str | None:
        """How the column is spelled: `"u.email"`, `"email"`, or `None` for `*`."""

        if self.column is None:
            return None

        return column_name(self.qualifier, self.column)

    @property
    def output(self) -> str | None:
        """The name the item's column goes by in the result, if it has one."""

        if self.alias is not None:
            return self.alias

        return None if self.is_aggregate else self.column

    def __str__(self) -> str:
        text: str = self.reference or "*"

        if self.function is not None:
            text = self.function.spell(self.reference)

        return text if self.alias is None else f"{text} AS {self.alias}"

@dataclass(frozen=True)
class Projection:
    items: tuple[Item, ...] = ()
    qualifier: str = ""
    """The alias an `<alias>.` has opened, until the next column consumes it."""

    def open(self, qualifier: str) -> "Projection":
        return replace(self, qualifier=qualifier)

    def add(self, item: Item) -> "Projection":
        """Record `item`, consuming the open qualifier."""

        return replace(self, items=self.items + (item,), qualifier="")

    def name_last(self, alias: str) -> "Projection | None":
        """Name the item just written, which has to be an unnamed aggregate."""

        if not self.items or not self.items[-1].is_aggregate or self.items[-1].alias is not None:
            return None

        return replace(self, items=self.items[:-1] + (replace(self.items[-1], alias=alias),))

    @property
    def last(self) -> Item | None:
        return self.items[-1] if self.items else None

    def outputs(self) -> tuple[str, ...]:
        """The output names of the items that have one, in order."""

        return tuple(item.output for item in self.items if item.output is not None)

    def aliases(self) -> frozenset[str]:
        """The names `AS` introduced."""

        return frozenset(item.alias for item in self.items if item.alias is not None)

    def plain(self) -> tuple[Item, ...]:
        """The items that are a column as it stands, which GROUP BY must cover."""

        return tuple(item for item in self.items if not item.is_aggregate)

    def has_aggregates(self) -> bool:
        return any(item.is_aggregate for item in self.items)

    def is_mixed(self) -> bool:
        """Whether plain columns stand beside aggregates, which demands GROUP BY."""

        return self.has_aggregates() and bool(self.plain())

    def bare_columns(self) -> frozenset[str]:
        """Every column the projection names without a qualifier."""

        return frozenset(
            item.column for item in self.items if item.column is not None and not item.qualifier
        )

    def __str__(self) -> str:
        return ", ".join(str(item) for item in self.items)
