"""The static description of the data: schema, names, types, operators, functions.

Nothing here changes while a statement is generated. Everything above reads it.
"""

from .names import (
    KEYWORDS,
    column_name,
    qualify,
    reference_name,
    sql_name,
    unqualify,
)
from .functions import ARGUMENT_KINDS, FUNCTIONS, Function, function_names
from .operators import (
    BINARY_OPERATORS,
    LITERALS,
    Operator,
    is_comparable,
    is_nullable,
    literal_for,
    operators_for,
)
from .parser import parse_schema
from .schema import Field, Reference, Schema, Table, Type
from .types import TypeClass, classify

__all__ = [
    "ARGUMENT_KINDS",
    "FUNCTIONS",
    "Function",
    "function_names",
    "BINARY_OPERATORS",
    "KEYWORDS",
    "LITERALS",
    "Field",
    "Operator",
    "Reference",
    "Schema",
    "Table",
    "Type",
    "TypeClass",
    "classify",
    "column_name",
    "is_comparable",
    "is_nullable",
    "literal_for",
    "operators_for",
    "parse_schema",
    "qualify",
    "reference_name",
    "sql_name",
    "unqualify",
]
