"""`CREATE TABLE` statements into a `Schema`, parsed with `sqlglot`."""

from __future__ import annotations

import sqlglot
import sqlglot.expressions as exp

from .schema import Field, Reference, Schema, Table, Type

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

def _parse_reference(kind: exp.Reference) -> Reference | None:
    target = kind.this

    if target is None or not target.expressions:
        return None

    return Reference(table=target.this.name, column=target.expressions[0].name)

def _parse_column(column: exp.ColumnDef, name: str, table: Table) -> Field:
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
        origin=Reference(table=name, column=column.name),
    )

def _parse_table(definition: exp.Schema, name: str) -> Table:
    table: Table = Table()

    for column in definition.expressions:
        if not isinstance(column, exp.ColumnDef):
            continue

        parsed: Field = _parse_column(column, name, table)

        table.fields[parsed.name] = parsed

        if parsed.is_unique:
            table.unique.append(parsed.name)

    return table

def parse_schema(sql: str) -> Schema | None:
    """Parse `CREATE TABLE` statements into a `Schema`.

    Returns `None` when nothing parsed, so a caller handed junk gets no schema
    rather than an empty one.
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

        name: str = definition.this.name

        schema.tables[name] = _parse_table(definition, name)

    if not schema.tables:
        return None

    return schema
