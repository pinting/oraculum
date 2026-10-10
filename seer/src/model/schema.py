"""The SQL schema model.

Columns keep their type, nullability, uniqueness and - the part the rest of the
modelling depends on - their foreign key `Reference` and their `origin`, which
between them are what `resolution.joins` builds the join graph from.

The resolvers only need the flat `table -> columns` view `get_fields` exposes;
everything richer is here for the join graph, the type gating of conditions
and the reserved name set an alias has to avoid. Parsing lives in `parser.py`,
so this module is the data alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

@dataclass(frozen=True)
class Type:
    name: str
    length: int | None = None

    def __str__(self) -> str:
        if self.length is None:
            return self.name

        return f"{self.name}({self.length})"

@dataclass(frozen=True)
class Reference:
    """A foreign key target."""

    table: str
    column: str

    def __str__(self) -> str:
        return f"{self.table}({self.column})"

@dataclass(frozen=True)
class Field:
    name: str
    type: Type
    is_nullable: bool = True
    is_unique: bool = False
    is_primary_key: bool = False
    reference: Reference | None = None
    """The column this one points at, if it is a foreign key."""

    origin: Reference | None = None
    """The schema column this one *is*: itself for a column the schema
    declared, the column it was projected from for one a derived table
    exports, and nothing for a value computed from others. A foreign key
    points at an origin, which is what lets a join follow a column through
    any number of derived tables."""

@dataclass
class Table:
    primary_key: str | None = None
    unique: list[str] = field(default_factory=list)
    fields: dict[str, Field] = field(default_factory=dict)

    def links(self, other: "Table") -> Iterator[tuple[Field, Field]]:
        """Every `(foreign key, target)` pair from a column here to one of `other`.

        A target is matched by its origin rather than by its table's name, so a
        key pointing at `users(id)` reaches `users.id` and equally the `id` of
        any derived table that projected it.
        """

        for column in self.fields.values():
            if column.reference is None:
                continue

            for target in other.fields.values():
                if target.origin == column.reference:
                    yield column, target

@dataclass
class Schema:
    tables: dict[str, Table] = field(default_factory=dict)

    def get_fields(self) -> dict[str, list[str]]:
        """The flat `table -> columns` view the resolvers work on."""

        return {name: list(table.fields.keys()) for name, table in self.tables.items()}

    def get_all_fields(self) -> set[str]:
        """Every column name in the schema, regardless of table."""

        names: set[str] = set()

        for table in self.tables.values():
            names.update(table.fields.keys())

        return names

    def get_names(self) -> set[str]:
        """Every name the schema defines: table names and column names."""

        names: set[str] = set(self.tables.keys())

        names.update(self.get_all_fields())

        return names

    def __bool__(self) -> bool:
        return bool(self.tables)
