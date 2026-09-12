"""Field selection state.

Port of `experiments/9-advanced-modelling/conflicts.py`: the facade that merges
`Root` (unqualified fields) and `Scopes` (aliased fields) into one interface
for the required and excluded table queries the FROM clause needs.

This is what `context.py` is built around, replacing the `ManyResolver` plus
`OneResolver` pair the Rust `Context` held.

Two adaptations for the token driven engine:

* Selections report failure with a bool instead of raising. The TUI the
  experiment was written for catches the exception and re-prompts; here a
  selector runs while the engine is speculatively expanding nodes.
* `copy()` gives every branch of the syntax graph its own state, sharing the
  parts that are immutable once built.
"""

from __future__ import annotations

from .root import Root
from .schema import Schema
from .scopes import Scopes, qualify, unqualify

class Conflicts:
    __slots__ = ("_root", "_scopes", "_schema", "_all_fields", "_used_fields")

    def __init__(self, schema: Schema | None = None) -> None:
        if schema is None:
            return

        fields: dict[str, list[str]] = schema.get_fields()

        self._schema = schema
        self._root = Root(fields)
        self._scopes = Scopes(fields)
        self._all_fields = frozenset(schema.get_all_fields())
        self._used_fields: tuple[str, ...] = ()

    def copy(self) -> "Conflicts":
        clone: Conflicts = Conflicts.__new__(Conflicts)

        clone._schema = self._schema
        clone._all_fields = self._all_fields
        clone._root = self._root.copy()
        clone._scopes = self._scopes.copy()
        clone._used_fields = self._used_fields

        return clone

    @property
    def schema(self) -> Schema:
        return self._schema

    @property
    def root(self) -> Root:
        return self._root

    @property
    def scopes(self) -> Scopes:
        return self._scopes

    def get_used_fields(self) -> tuple[str, ...]:
        return self._used_fields

    def use_field(self, scope: str, field: str) -> bool:
        """Select `field`, qualified by `scope` when it is not empty."""

        if not scope:
            applied: bool = self._root.use_field(field)
        else:
            applied = self._scopes.use_field(scope, field)

        if not applied:
            return False

        self._used_fields = self._used_fields + (f"{scope}.{field}" if scope else field,)

        return True

    def get_all_fields(self) -> frozenset[str]:
        return self._all_fields

    def get_fields(self, scope: str = "") -> frozenset[str]:
        """Fields still selectable in `scope`.

        An alias that has not been used yet may still become any table, so it
        offers every field in the schema.
        """

        if not scope:
            return self._root.get_fields()

        fields: frozenset[str] | None = self._scopes.get_fields(scope)

        if fields is None:
            return self._all_fields

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
        """Satisfy a required node, named `"table"` or `"table alias"`."""

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
            f"Selected fields  = {', '.join(self._used_fields)}\n"
            f"Excluded fields  = {', '.join(sorted(self.get_excluded_fields()))}\n"
            f"Root tables      = {self._root}\n"
            f"Scopes tables    = {self._scopes}\n"
            f"Excluded tables  = {', '.join(sorted(self.get_excluded_tables()))}"
        )

    def __repr__(self) -> str:
        return f"Conflicts(required={sorted(self.get_required_tables())})"
