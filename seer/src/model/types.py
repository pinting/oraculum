"""Type classes: the coarse partition of SQL types the generator reasons in.

SQL's own type system is a lattice of implicit coercions no two dialects agree
on; what a generator needs is only enough structure to refuse `id LIKE 'a%'`
and `email < 5`, and one flat classification gives that. `UNKNOWN` is a class
of its own rather than a wildcard, so a type the parser did not recognise
compares to nothing but another of its kind - a refusal is the safe direction
to be wrong in.
"""

from __future__ import annotations

from enum import Enum

from .schema import Type

class TypeClass(Enum):
    NUMERIC = "numeric"
    TEXT = "text"
    TEMPORAL = "temporal"
    BOOLEAN = "boolean"
    BINARY = "binary"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value

# The spellings `parser._parse_type` produces: sqlglot reports a type name
# through its `DataType.Type` enum and the parser upper cases it. Aliases that
# sqlglot happens to normalise away are listed anyway, since the cost is a
# dictionary entry and the alternative is a silent `UNKNOWN`.
_NAMES: dict[TypeClass, tuple[str, ...]] = {
    TypeClass.NUMERIC: (
        "TINYINT", "SMALLINT", "MEDIUMINT", "INT", "INTEGER", "BIGINT",
        "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "REAL", "MONEY",
        "SERIAL", "SMALLSERIAL", "BIGSERIAL",
    ),
    TypeClass.TEXT: (
        "CHAR", "NCHAR", "VARCHAR", "NVARCHAR", "TEXT",
        "TINYTEXT", "MEDIUMTEXT", "LONGTEXT", "CLOB", "UUID",
    ),
    TypeClass.TEMPORAL: (
        "DATE", "DATETIME", "DATETIME64", "TIME",
        "TIMESTAMP", "TIMESTAMPTZ", "TIMESTAMPLTZ", "TIMESTAMPNTZ",
    ),
    TypeClass.BOOLEAN: ("BOOLEAN", "BOOL", "BIT"),
    TypeClass.BINARY: (
        "BINARY", "VARBINARY", "BYTEA",
        "BLOB", "TINYBLOB", "MEDIUMBLOB", "LONGBLOB",
    ),
}

CLASSES: dict[str, TypeClass] = {
    name: kind for kind, names in _NAMES.items() for name in names
}

# A set of classes a value may have, which is how a position that takes only
# some of them - a function argument, a side of a comparison - is described.
Kinds = frozenset[TypeClass]

def classify(type: Type) -> TypeClass:
    """Which class `type` falls in; `UNKNOWN` for a name not listed."""

    return CLASSES.get(type.name.upper(), TypeClass.UNKNOWN)
