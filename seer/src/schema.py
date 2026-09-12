"""SQL schema model and parsing.

Port of `experiments/9-advanced-modelling/schema.py`, which replaced the
line-based scanner of `seer/src/schema.rs` with a real parse via `sqlglot`.

The model is richer than the `dict[str, list[str]]` the Rust version carried:
columns keep their type, nullability, uniqueness and -- the part the rest of
the port depends on -- their foreign key `Reference`, which is what
`relationships.py` builds the join graph from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

import sqlglot
import sqlglot.expressions as exp

# Words an identifier must not spell to be usable as an alias.
#
# Only the keywords the generated language can actually emit have to be here
# for the grammar to stay unambiguous; the rest are listed because an alias
# that shadows a SQL keyword is a bad alias whether or not seer would trip
# over it. Both cases are excluded at the point of use -- SQL keywords are
# case insensitive -- but mixed case spellings are not, since no vocabulary
# token produces them at the start of an identifier in practice.
RESERVED: frozenset[str] = frozenset({
    "ALL", "AND", "AS", "ASC", "BETWEEN", "BY", "CASE", "CROSS", "DESC",
    "DISTINCT", "ELSE", "END", "EXISTS", "FROM", "FULL", "GROUP", "HAVING",
    "IN", "INNER", "IS", "JOIN", "LEFT", "LIKE", "LIMIT", "NOT", "NULL",
    "OFFSET", "ON", "OR", "ORDER", "OUTER", "RIGHT", "SELECT", "THEN",
    "UNION", "WHEN", "WHERE",
})

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

@dataclass
class Table:
    primary_key: str | None = None
    unique: list[str] = field(default_factory=list)
    fields: dict[str, Field] = field(default_factory=dict)

    def references(self, table: str) -> Iterator[Field]:
        """Every field of this table pointing at `table`."""

        for column in self.fields.values():
            if column.reference is not None and column.reference.table == table:
                yield column

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

def _parse_type(column: exp.ColumnDef) -> Type:
    kind = column.args.get("kind")

    if kind is None:
        return Type(name="UNKNOWN")

    name: str = kind.this.value if hasattr(kind.this, "value") else str(kind.this)
    length: int | None = None

    if kind.expressions:
        param = kind.expressions[0]

        if isinstance(param, exp.DataTypeParam):
            try:
                length = int(param.this.name)
            except (AttributeError, ValueError):
                length = None

    return Type(name=name.upper(), length=length)

def _parse_column(column: exp.ColumnDef, table: Table) -> Field:
    is_nullable: bool = True
    is_unique: bool = False
    is_primary_key: bool = False
    reference: Reference | None = None

    for constraint in column.constraints:
        kind = constraint.args.get("kind")

        if isinstance(kind, exp.NotNullColumnConstraint):
            is_nullable = False
        elif isinstance(kind, exp.UniqueColumnConstraint):
            is_unique = True
        elif isinstance(kind, exp.PrimaryKeyColumnConstraint):
            is_primary_key = True
            table.primary_key = column.name
        elif isinstance(kind, exp.Reference):
            reference = _parse_reference(kind)

    return Field(
        name=column.name,
        type=_parse_type(column),
        is_nullable=is_nullable,
        is_unique=is_unique,
        is_primary_key=is_primary_key,
        reference=reference,
    )

def _parse_reference(kind: exp.Reference) -> Reference | None:
    target = kind.this

    if target is None or not target.expressions:
        return None

    return Reference(table=target.this.name, column=target.expressions[0].name)

def parse_schema(sql: str) -> Schema | None:
    """Parse `CREATE TABLE` statements into a `Schema`.

    Returns `None` when nothing parsed, matching the `Option` the Rust version
    returned so the callers keep their shape.
    """

    schema: Schema = Schema()

    try:
        statements = sqlglot.parse(sql)
    except sqlglot.ParseError:
        return None

    for statement in statements:
        if not isinstance(statement, exp.Create) or statement.args.get("kind") != "TABLE":
            continue

        definition = statement.this

        if definition is None:
            continue

        table: Table = Table()

        for column in definition.expressions:
            if not isinstance(column, exp.ColumnDef):
                continue

            parsed: Field = _parse_column(column, table)

            table.fields[parsed.name] = parsed

            if parsed.is_unique:
                table.unique.append(parsed.name)

        schema.tables[definition.this.name] = table

    if not schema.tables:
        return None

    return schema
