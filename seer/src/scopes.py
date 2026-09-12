"""Registry of alias namespaces.

A scope is created lazily the first time an alias is used. Table names are
reported qualified as `"<table> <alias>"`, which is the node naming the join
graph in `relationships.py` expects and what distinguishes `users` from
`users u` when both appear in one query.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .scope import Scope

def qualify(table: str, alias: str) -> str:
    """`"users u"` for an aliased table, `"users"` for a bare one."""

    if not alias:
        return table

    return f"{table} {alias}"

def sql_name(node: str) -> str:
    """How a node is written in a FROM or JOIN clause: `"comments AS cm"`."""

    table, alias = unqualify(node)

    if not alias:
        return table

    return f"{table} AS {alias}"

def unqualify(node: str) -> tuple[str, str]:
    """Split a node name back into `(table, alias)`; alias is `""` if bare."""

    parts: list[str] = node.split()

    if len(parts) == 1:
        return parts[0], ""

    return parts[0], parts[1]

def reference_name(node: str) -> str:
    """How a node is referred to once it is in the clause: `"c"`, `"users"`.

    These tokens are emitted verbatim, so they have to be valid SQL: an aliased
    node is referenced by its alias and a bare one by its table name. It is the
    qualifier of every column reference the node supplies, which is what an
    `ON` clause and a `WHERE` operand are both written from.
    """

    table, alias = unqualify(node)

    return alias if alias else table

class Scopes:
    __slots__ = ("_scopes", "_schema")

    def __init__(self, schema: Mapping[str, Sequence[str]] | None = None) -> None:
        self._scopes: dict[str, Scope] = {}
        self._schema: Mapping[str, Sequence[str]] = schema if schema is not None else {}

    def copy(self) -> "Scopes":
        clone: Scopes = Scopes.__new__(Scopes)

        clone._schema = self._schema
        clone._scopes = {alias: scope.copy() for alias, scope in self._scopes.items()}

        return clone

    def names(self) -> list[str]:
        return sorted(self._scopes)

    def __contains__(self, alias: str) -> bool:
        return alias in self._scopes

    def use_field(self, scope: str, field: str) -> bool:
        """Narrow the alias by `field`, creating the scope on first use."""

        resolver: Scope | None = self._scopes.get(scope)

        if resolver is None:
            resolver = Scope(self._schema)

            if not resolver.use_field(field):
                return False

            self._scopes[scope] = resolver

            return True

        return resolver.use_field(field)

    def get_fields(self, scope: str) -> frozenset[str] | None:
        resolver: Scope | None = self._scopes.get(scope)

        if resolver is None:
            return None

        return resolver.get_fields()

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
