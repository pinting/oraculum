"""Registry of alias namespaces.

A scope is created lazily the first time an alias is used. Table names are
reported qualified as `"<table> <alias>"` (`model.names.qualify`), which is the
node naming the join graph in `relationships.py` expects and what distinguishes `users` from
`users u` when both appear in one query.
"""

from __future__ import annotations

from ..model import qualify
from .columns import ColumnIndex, Kinds
from .scope import Scope

class Scopes:
    __slots__ = ("_scopes", "_index")

    def __init__(self, index: ColumnIndex | None = None) -> None:
        if index is None:
            return

        self._scopes: dict[str, Scope] = {}
        self._index: ColumnIndex = index

    def copy(self) -> "Scopes":
        clone: Scopes = Scopes.__new__(Scopes)

        clone._index = self._index
        clone._scopes = {alias: scope.copy() for alias, scope in self._scopes.items()}

        return clone

    def names(self) -> list[str]:
        return sorted(self._scopes)

    def __contains__(self, alias: str) -> bool:
        return alias in self._scopes

    def open(self) -> list[tuple[str, frozenset[str]]]:
        """Every alias not placed yet, with the tables it may still be, sorted."""

        return [
            (alias, resolver.get_required_tables())
            for alias, resolver in sorted(self._scopes.items())
            if not resolver.is_satisfied()
        ]

    def candidates(self, scope: str, field: str, kinds: Kinds | None = None) -> frozenset[str]:
        """The tables `scope` could be after selecting `field` in it."""

        resolver: Scope | None = self._scopes.get(scope)
        owners: frozenset[str] = self._index.owners(field, kinds)

        return owners if resolver is None else resolver.get_required_tables() & owners

    def use_field(self, scope: str, field: str, kinds: Kinds | None = None) -> bool:
        """Narrow the alias by `field`, creating the scope on first use."""

        resolver: Scope | None = self._scopes.get(scope)

        if resolver is None:
            resolver = Scope(self._index)

            if not resolver.use_field(field, kinds):
                return False

            self._scopes[scope] = resolver

            return True

        return resolver.use_field(field, kinds)

    def get_fields(self, scope: str, kinds: Kinds | None = None) -> frozenset[str] | None:
        """The fields `scope` still offers, or `None` for an alias not yet opened."""

        resolver: Scope | None = self._scopes.get(scope)

        if resolver is None:
            return None

        return resolver.get_fields(kinds)

    def get_excluded_fields(self, scope: str) -> frozenset[str] | None:
        resolver: Scope | None = self._scopes.get(scope)

        if resolver is None:
            return None

        return resolver.get_excluded_fields()

    def get_required_tables(self) -> frozenset[str]:
        result: set[str] = set()

        for alias, resolver in self._scopes.items():
            for name in resolver.get_required_tables():
                result.add(qualify(name, alias))

        return frozenset(result)

    def get_excluded_tables(self) -> frozenset[str]:
        result: set[str] = set()

        for alias, resolver in self._scopes.items():
            for table in resolver.get_excluded_tables():
                result.add(qualify(table, alias))

        return frozenset(result)

    def use_table(self, scope: str, table: str) -> bool:
        resolver: Scope | None = self._scopes.get(scope)

        if resolver is None:
            return False

        return resolver.use_table(table)

    def is_satisfied(self) -> bool:
        return all(resolver.is_satisfied() for resolver in self._scopes.values())

    def __str__(self) -> str:
        if not self._scopes:
            return ""

        return "; ".join(f"{name} = {scope}" for name, scope in sorted(self._scopes.items()))

    def __repr__(self) -> str:
        return f"Scopes({self})"
