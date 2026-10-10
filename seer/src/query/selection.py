"""The PROJECTION part of a query: what is selected, and what that demands.

`Projection` records the items; `Conflicts` turns each column into a demand on
the tables. They change together - every item narrows the table space - so
they are one part, and this is the only place either is written.

The naming rules sit here too, because every name the projection invents is
checked against what the projection has already introduced: see `names.py`.

A **derived** selection - the body of a `WITH` definition - exports its items
as the columns of a table, so it has two rules more: no two items may output
the same name, and every aggregate has to be named, since a column needs one.
"""

from __future__ import annotations

from ..model import Function, Schema
from ..resolution import Conflicts
from .names import Exclusion, NameUse
from .projection import Item, Projection

class Selection:
    __slots__ = ("_projection", "_conflicts", "_reserved", "_derived")

    def __init__(
        self,
        schema: Schema | None = None,
        base: Exclusion = Exclusion(),
        derived: bool = False,
    ) -> None:
        if schema is None:
            return

        self._projection: Projection = Projection()
        self._conflicts: Conflicts = Conflicts(schema)
        self._reserved: Exclusion = base
        self._derived: bool = derived

    def copy(self) -> "Selection":
        clone: Selection = Selection.__new__(Selection)

        clone._projection = self._projection
        clone._conflicts = self._conflicts.copy()
        clone._reserved = self._reserved
        clone._derived = self._derived

        return clone

    @property
    def projection(self) -> Projection:
        return self._projection

    @property
    def conflicts(self) -> Conflicts:
        return self._conflicts

    @property
    def qualifier(self) -> str:
        """The alias an `<alias>.` has opened, until the next column consumes it."""

        return self._projection.qualifier

    # -- what may be written ----------------------------------------------

    def reserved(self, use: NameUse) -> Exclusion:
        """What a name invented for `use` may not spell; see `names.py`."""

        aliases: frozenset[str] = self._projection.aliases()
        scopes: list[str] = self._conflicts.scopes.names()

        if use is NameUse.QUALIFIER:
            return self._reserved.including(aliases).respelling(scopes)

        return self._reserved.including(aliases, scopes)

    def columns(self) -> list[str]:
        """Columns a plain item may name, sorted so expansion is reproducible.

        In a derived selection a column whose name is already an output is not
        offered again, however it would be qualified.
        """

        columns: frozenset[str] = self._conflicts.get_fields(self.qualifier)

        if self._derived:
            columns = columns - frozenset(self._projection.outputs())

        return sorted(columns)

    def arguments(self, function: Function) -> list[str]:
        """Columns `function` may be applied to."""

        return sorted(self._conflicts.get_fields(self.qualifier, function.accepts))

    def can_end_item(self) -> bool:
        """Whether the item just written is complete as it stands.

        Only an unnamed aggregate of a derived selection is not: the table it
        exports needs a name for the column.
        """

        last: Item | None = self._projection.last

        return not (self._derived and last is not None and last.output is None)

    # -- writing it -------------------------------------------------------

    def open(self, qualifier: str) -> bool:
        if not self.reserved(NameUse.QUALIFIER).allows(qualifier):
            return False

        self._projection = self._projection.open(qualifier)

        return True

    def column(self, column: str) -> bool:
        qualifier: str = self.qualifier

        if self._derived and column in self._projection.outputs():
            return False

        if not self._conflicts.use_field(qualifier, column):
            return False

        self._projection = self._projection.add(Item(qualifier, column))

        return True

    def aggregate(self, function: Function, column: str | None) -> bool:
        """`function` over `column`, or over `*` where `column` is `None`."""

        qualifier: str = self.qualifier

        if column is None:
            if not function.star or qualifier:
                return False
        elif not self._conflicts.use_field(qualifier, column, function.accepts):
            return False

        self._projection = self._projection.add(Item(qualifier, column, function))

        return True

    def name(self, alias: str) -> bool:
        """Name the aggregate just written."""

        if not self.reserved(NameUse.OUTPUT).allows(alias):
            return False

        named: Projection | None = self._projection.name_last(alias)

        if named is None:
            return False

        self._projection = named

        return True

    def __str__(self) -> str:
        return f"Selected items   = {self._projection}\n{self._conflicts}"
