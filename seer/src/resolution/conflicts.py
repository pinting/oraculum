"""Field selection state.

The facade that merges `Root` (unqualified fields) and `Scopes` (aliased
fields) into one interface for the required and excluded table queries the FROM
clause needs. This is what the projection of a query is resolved against.

Two properties the token driven engine depends on:

* Selections report failure with a bool instead of raising, because a selector
  runs while the engine is speculatively expanding nodes and a rejected
  alternative is ordinary rather than exceptional.
* `copy()` gives every branch of the syntax graph its own state, sharing the
  parts that are immutable once built.

What was selected is not recorded here - the projection of the query keeps
the items, this keeps only what they imply about the tables.
"""

from __future__ import annotations

from ..model import Schema, unqualify
from .columns import ColumnIndex, Kinds
from .root import Root
from .scopes import Scopes

class Conflicts:
    __slots__ = ("_index", "_root", "_scopes")

    def __init__(self, schema: Schema | None = None) -> None:
        if schema is None:
            return

        self._index: ColumnIndex = ColumnIndex(schema)
        self._root = Root(self._index)
        self._scopes = Scopes(self._index)

    def copy(self) -> "Conflicts":
        clone: Conflicts = Conflicts.__new__(Conflicts)

        clone._index = self._index
        clone._root = self._root.copy()
        clone._scopes = self._scopes.copy()

        return clone

    @property
    def index(self) -> ColumnIndex:
        return self._index

    @property
    def root(self) -> Root:
        return self._root

    @property
    def scopes(self) -> Scopes:
        return self._scopes

    def use_field(self, scope: str, field: str, kinds: Kinds | None = None) -> bool:
        """Select `field`, qualified by `scope` when it is not empty.

        `kinds` restricts the classes the column may have, which is what
        handing it to a function does.
        """

        if not scope:
            return self._root.use_field(field, kinds)

        return self._scopes.use_field(scope, field, kinds)

    def get_fields(self, scope: str = "", kinds: Kinds | None = None) -> frozenset[str]:
        """Fields still selectable in `scope`.

        An alias that has not been used yet may still become any table, so it
        offers every field in the schema - of an accepted class, for an
        argument.
        """

        if not scope:
            return self._root.get_fields(kinds)

        fields: frozenset[str] | None = self._scopes.get_fields(scope, kinds)

        if fields is None:
            return self._index.fields(kinds)

        return fields

    def get_excluded_fields(self, scope: str = "") -> frozenset[str]:
        if not scope:
            return self._root.get_excluded_fields()

        fields: frozenset[str] | None = self._scopes.get_excluded_fields(scope)

        if fields is None:
            return frozenset()

        return fields

    def get_required_tables(self) -> frozenset[str]:
        """Nodes the FROM clause still has to supply, as `"table"` or `"table alias"`."""

        return self._root.get_required_tables() | self._scopes.get_required_tables()

    def get_excluded_tables(self) -> frozenset[str]:
        return self._root.get_excluded_tables() | self._scopes.get_excluded_tables()

    def use_table(self, node: str) -> bool:
        """Satisfy a node, named `"table"` or `"table alias"`."""

        table, alias = unqualify(node)

        if not alias:
            return self._root.use_table(table)

        if not self._scopes.use_table(alias, table):
            return False

        # The table is present under an alias, so root constraints naming it
        # are satisfied too.
        if not self._root.is_satisfied():
            self._root.use_table(table)

        return True

    def is_satisfied(self) -> bool:
        return self._root.is_satisfied() and self._scopes.is_satisfied()

    def __str__(self) -> str:
        return (
            f"Satisfied        = {self.is_satisfied()}\n"
            f"Excluded fields  = {', '.join(sorted(self.get_excluded_fields()))}\n"
            f"Root tables      = {self._root}\n"
            f"Scopes tables    = {self._scopes}\n"
            f"Excluded tables  = {', '.join(sorted(self.get_excluded_tables()))}"
        )

    def __repr__(self) -> str:
        return f"Conflicts(required={sorted(self.get_required_tables())})"
