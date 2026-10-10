"""The PROJECTION part of a query: what is selected, and what that demands.

`Projection` records the items; `Conflicts` turns each column into a demand on
the tables. They change together - every column narrows the table space - so
they are one part, and this is the only place either is written.

An item is an expression, and its columns are demanded as they are written,
before the item is complete: `LOWER(` has to know that what follows is text,
and the column inside it narrows the tables the moment it is taken. A column
written where nothing fixed its class may be narrowed afterwards - `id + 1`
only learns `id` is numeric at the `+` - and narrowing it is demanding it
again under the narrower class, which the algebra takes as one more factor.

The naming rules sit here too, because every name the projection invents is
checked against what the projection has already introduced: see `names.py`.

What the frame of the query asks of its items - names, a shape, simplicity -
is its `Contract`, which the selection consults before it adds an item and
before it lets the projection be left.
"""

from __future__ import annotations

from ..model import LITERAL_CLASSES, Kinds, Schema
from ..resolution import Conflicts
from .expression import Column, Expr
from .contract import Contract
from .names import Exclusion, NameUse
from .placement import placeable
from .projection import Projection

class Selection:
    __slots__ = ("_schema", "_projection", "_conflicts", "_bare", "_reserved", "_contract")

    def __init__(
        self,
        schema: Schema | None = None,
        base: Exclusion = Exclusion(),
        contract: Contract = Contract(),
    ) -> None:
        if schema is None:
            return

        self._schema: Schema = schema
        self._projection: Projection = Projection()
        self._conflicts: Conflicts = Conflicts(schema)
        self._bare: frozenset[str] = frozenset()
        self._reserved: Exclusion = base
        self._contract: Contract = contract

    def copy(self) -> "Selection":
        clone: Selection = Selection.__new__(Selection)

        clone._schema = self._schema
        clone._projection = self._projection
        clone._conflicts = self._conflicts.copy()
        clone._bare = self._bare
        clone._reserved = self._reserved
        clone._contract = self._contract

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

    @property
    def is_simple(self) -> bool:
        return self._contract.simple

    @property
    def once(self) -> frozenset[str]:
        """The tables the FROM clause may place one node of at most."""

        return self._contract.once

    def bare_columns(self) -> frozenset[str]:
        """Every column named without a qualifier so far, the item being written's too."""

        return self._bare

    # -- what may be written ----------------------------------------------

    def columns(self, kinds: Kinds | None = None, qualifier: str | None = None) -> list[str]:
        """Columns that may be written next, of `kinds` where given, sorted."""

        scope: str = self.qualifier if qualifier is None else qualifier
        columns: frozenset[str] = self._conflicts.get_fields(scope, kinds)

        return sorted(column for column in columns if self._keeps_placeable(scope, column, kinds))

    def _keeps_placeable(self, scope: str, column: str, kinds: Kinds | None) -> bool:
        """Whether selecting `column` in `scope` leaves a FROM clause to write; see `placement.py`."""

        # Without an alias there is nothing the algebra does not see already:
        # two tables supplying one bare column are mutually exclusive in it,
        # and every table is placed once.
        if not scope and not self._conflicts.scopes.names():
            return True

        trial: Conflicts = self._conflicts.copy()

        if not trial.use_field(scope, column, kinds):
            return False

        bare: frozenset[str] = self._bare if scope else self._bare | {column}

        return placeable(self._schema, trial, bare, (), self._contract.once)

    # What an alias that has not been opened yet is called while it is asked
    # about: no identifier spells it, so it is never one that has.
    FRESH: str = "\0"

    def can_open(self, kinds: Kinds | None = None) -> bool:
        """Whether a new alias would have a column to offer here."""

        return bool(self.columns(kinds, self.FRESH))

    def useful(self, kinds: Kinds | None = None) -> list[str]:
        """The aliases already opened that still have a column to offer here."""

        return [scope for scope in self._conflicts.scopes.names() if self.columns(kinds, scope)]

    def reserved(self, use: NameUse, kinds: Kinds | None = None) -> Exclusion:
        """What a name invented for `use` may not spell; see `names.py`.

        A qualifier may repeat an alias already opened - but only one that
        still has a column to offer where it is being written, or the dot
        after it would lead nowhere.
        """

        aliases: frozenset[str] = self._projection.aliases()
        scopes: list[str] = self._conflicts.scopes.names()

        if use is NameUse.QUALIFIER:
            useful: list[str] = self.useful(kinds)
            useless: list[str] = [scope for scope in scopes if scope not in useful]

            return self._reserved.including(aliases, useless).respelling(useful)

        return self._reserved.including(aliases, scopes)

    def can_qualify(self, kinds: Kinds | None = None) -> bool:
        """Whether `<alias>.` may be written here: some alias has a column to offer."""

        return self.can_open(kinds) or bool(self.useful(kinds))

    def can_supply(self, kinds: Kinds | None) -> bool:
        """Whether a value of `kinds` can be written at all: a literal, or some column."""

        if kinds is None or any(kind in kinds for kind in LITERAL_CLASSES):
            return True

        return bool(self.columns(kinds, "")) or self.can_qualify(kinds)

    def can_narrow(self, columns: tuple[Column, ...], kinds: Kinds) -> bool:
        """Whether every one of `columns` can still be of `kinds`, all at once."""

        trial: Conflicts = self._conflicts.copy()

        if not all(trial.use_field(column.qualifier, column.name, kinds) for column in columns):
            return False

        return placeable(self._schema, trial, self._bare, (), self._contract.once)

    @property
    def allows_aggregates(self) -> bool:
        return not self._contract.simple

    def item_kinds(self) -> Kinds | None:
        """The classes the next item may have, where the shape fixes them."""

        return self._contract.kinds_at(len(self._projection.items))

    def admits(self, expr: Expr) -> bool:
        """Whether `expr` may be added as the next item."""

        return self._contract.admits(self._projection, expr)

    def needs_name(self, expr: Expr) -> bool:
        """Whether `expr` may only be added with an `AS`; see `contract.py`."""

        return self._contract.needs_name(self._projection, expr)

    def can_follow(self) -> bool:
        """Whether another item may come after the one being written."""

        following: Kinds | None = self._contract.kinds_at(len(self._projection.items) + 1)

        return self._contract.has_room(self._projection, 1) and self.can_supply(following)

    def can_end(self) -> bool:
        """Whether the item being written may be the last."""

        return self._contract.may_end_with_next(self._projection)

    def is_complete(self) -> bool:
        """Whether the projection may be left for the FROM clause."""

        if not self._projection.items or self._projection.qualifier:
            return False

        return self._contract.is_met(self._projection)

    # -- writing it -------------------------------------------------------

    def open(self, qualifier: str) -> bool:
        if not self.reserved(NameUse.QUALIFIER).allows(qualifier):
            return False

        self._projection = self._projection.open(qualifier)

        return True

    def column(self, column: str, kinds: Kinds | None = None) -> bool:
        """Demand `column`, under the open qualifier, as a value of `kinds`."""

        if not self._conflicts.use_field(self.qualifier, column, kinds):
            return False

        if not self.qualifier:
            self._bare = self._bare | {column}

        self._projection = self._projection.consume()

        return True

    def narrow(self, columns: tuple[Column, ...], kinds: Kinds) -> bool:
        """Demand `columns` again, now that their value has to be of `kinds`."""

        return all(self._conflicts.use_field(column.qualifier, column.name, kinds) for column in columns)

    def add(self, expr: Expr) -> bool:
        if not self.admits(expr):
            return False

        self._projection = self._projection.add(expr)

        return True

    def name(self, alias: str) -> bool:
        """Name the item just written."""

        if not self.reserved(NameUse.OUTPUT).allows(alias):
            return False

        named: Projection | None = self._projection.name_last(alias)

        if named is None:
            return False

        self._projection = named

        return True

    def deduplicate(self) -> bool:
        if self._contract.simple or self._projection.items:
            return False

        self._projection = self._projection.deduplicate()

        return True

    def __str__(self) -> str:
        return f"Selected items   = {self._projection}\n{self._conflicts}"
