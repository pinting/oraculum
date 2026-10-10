"""What a query can see: the schema, and every virtual table stacked below it.

`WITH a AS (...), b AS (...) SELECT ...` is a stack. Each definition is a
virtual table of its own, written over everything defined before it, and once
it is closed it is pushed under whatever comes next:

    main  ->  b  ->  a  ->  (the schema)

Every virtual table holds the stack below it as a `Catalog`, and the catalog is
how the stack is read. It folds the stack into the two things a query needs:

* one `Schema` holding the physical tables and every export below, so each
  resolver works over derived tables exactly as over declared ones;
* the reserved names of the whole stack - every table and column any layer
  defines - which an invented name may spell none of.

A closed virtual table never changes, so a stack is persistent: pushing builds
a new catalog over the old one, and every branch of the syntax graph shares the
layers below it.

A recursive definition reads itself before it is closed, which a stack of
closed layers cannot express. So a catalog may carry one **provisional**
table besides its layers - the definition, as the members written so far
export it - which its schema and reserved names include, but which is no
layer: pushing the definition once it closes stacks it on the catalog without
the provisional table, `base`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from ..model import Schema, Table
from .names import Exclusion, base_reserved

if TYPE_CHECKING:
    from .virtual import VirtualTable

class Catalog:
    __slots__ = ("_physical", "_top", "_provisional", "_base", "_schema", "_reserved")

    def __init__(
        self,
        physical: Schema,
        top: "VirtualTable | None" = None,
        provisional: tuple[str, Table] | None = None,
        base: "Catalog | None" = None,
    ) -> None:
        self._physical = physical
        self._top = top
        self._provisional = provisional
        self._base: Catalog = self if base is None else base

        tables: dict[str, Table] = dict(physical.tables)

        # Bottom up, so the order the tables are listed in is the order they
        # were defined in.
        for layer in reversed(tuple(self.layers())):
            assert layer.name is not None and layer.name not in tables

            tables[layer.name] = layer.export()

        if provisional is not None:
            name, table = provisional

            assert name not in tables

            tables[name] = table

        self._schema = Schema(tables)
        self._reserved: Exclusion = base_reserved(self._schema)

    @property
    def physical(self) -> Schema:
        """The schema as declared, with nothing derived in it."""

        return self._physical

    @property
    def top(self) -> "VirtualTable | None":
        """The virtual table stacked last, if any."""

        return self._top

    @property
    def base(self) -> "Catalog":
        """This catalog without its provisional table, which is where a layer is pushed."""

        return self._base

    @property
    def provisional(self) -> str | None:
        """The name of the definition being read before it is closed, if any."""

        return None if self._provisional is None else self._provisional[0]

    def reading(self, name: str, table: Table) -> "Catalog":
        """This catalog, with the definition `name` readable as `table` before it closes."""

        return Catalog(self._physical, self._top, (name, table), self._base)

    @property
    def schema(self) -> Schema:
        """The physical tables and every export of the stack."""

        return self._schema

    @property
    def reserved(self) -> Exclusion:
        """Keywords, functions, and every table and column of the stack."""

        return self._reserved

    def layers(self) -> Iterator["VirtualTable"]:
        """Every stacked virtual table, the most recent first."""

        layer: "VirtualTable | None" = self._top

        while layer is not None:
            yield layer

            layer = layer.below

    def names(self) -> tuple[str, ...]:
        """The names the stack exports under, in definition order."""

        return tuple(reversed([layer.name for layer in self.layers() if layer.name is not None]))

    def push(self, query: "VirtualTable") -> "Catalog":
        """The catalog with the closed, named `query` stacked on top."""

        assert query.name is not None and query.is_closed()

        return Catalog(self._base._physical, query)

    def __str__(self) -> str:
        return ", ".join(
            f"{name}({', '.join(self._schema.tables[name].fields)})" for name in self.names()
        )
