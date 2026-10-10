"""Frame: where a query stands in its statement.

A query is written the same way wherever it stands, but what it has to produce
depends on where that is:

* the **main** query produces whatever it likes;
* the body of a **definition** exports a table, so every column it produces
  needs a name, and no two the same one - unless the definition's column list
  names them instead;
* a later **member** of a compound has to produce the shape of the first, and
  needs no names at all, since the first member's are the compound's;
* a **recursive** member - a member of a `WITH RECURSIVE` definition after a
  `UNION` - may read the definition it belongs to, and has to stay a simple
  select to do so.

A frame says which of these a query is, and the virtual table reads off it
the rules its parts apply.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .compound import Compound, SetOperator
from .contract import Contract
from .shape import Shape

if TYPE_CHECKING:
    from .virtual import VirtualTable

@dataclass(frozen=True)
class Frame:
    name: str | None = None
    """The definition the query is the body of; `None` for the main query."""

    columns: tuple[str, ...] = ()
    """The definition's column list, if it wrote one."""

    compound: Compound | None = None
    """The members written before this one, if it is a later member."""

    recursive: bool = False
    """Whether the query may read the definition it belongs to."""

    @property
    def is_derived(self) -> bool:
        return self.name is not None

    @property
    def named(self) -> bool:
        """Whether every column the query produces needs a name of its own."""

        return self.is_derived and not self.columns and self.compound is None

    def shape(self) -> Shape | None:
        if self.compound is not None:
            return Shape.of(self.compound.result())

        if self.columns:
            return Shape.arity(len(self.columns))

        return None

    def contract(self, provisional: str | None = None) -> Contract:
        """What the query's projection owes this frame; see `contract.py`.

        `provisional` is the definition a recursive member reads, which it may
        place once at most.
        """

        once: frozenset[str] = frozenset({provisional}) if self.recursive and provisional else frozenset()

        return Contract(named=self.named, shape=self.shape(), simple=self.recursive, once=once)

    def names(self) -> tuple[str, ...]:
        """What the exported columns are called, where the frame decides it."""

        if self.columns:
            return self.columns

        if self.compound is not None:
            return tuple(output.name or "" for output in self.compound.result())

        return ()

    def after(self, member: "VirtualTable", operator: SetOperator, recursive: bool) -> "Frame":
        """The frame of the member `operator` opens after the closed `member`.

        Where the statement is `WITH RECURSIVE`, a union inside a definition
        opens a member that may read the definition itself.
        """

        compound: Compound = (
            Compound.starting(member, operator)
            if self.compound is None
            else self.compound.joined(member, operator)
        )

        return Frame(
            self.name,
            self.columns,
            compound,
            recursive and self.is_derived and operator.is_union,
        )
