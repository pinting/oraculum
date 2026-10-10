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
from .functions import (
    AGGREGATES,
    CAST,
    COALESCE,
    COUNT,
    FUNCTIONS,
    NUMERIC,
    RANKINGS,
    SCALARS,
    Function,
    Nulls,
    Role,
    function_names,
)
from .operators import (
    BINARY_OPERATORS,
    LITERAL_CLASSES,
    LITERAL_TYPES,
    LITERALS,
    NULLITY,
    Arity,
    Operator,
    comparisons,
    is_comparable,
    is_nullable,
    literal_for,
    operators_for,
)
from .parser import parse_schema
from .schema import Field, Reference, Schema, Table, Type
from .types import Kinds, TypeClass, classify

__all__ = [
    "AGGREGATES",
    "CAST",
    "COALESCE",
    "COUNT",
    "FUNCTIONS",
    "NUMERIC",
    "RANKINGS",
    "SCALARS",
    "Function",
    "Nulls",
    "Role",
    "function_names",
    "BINARY_OPERATORS",
    "KEYWORDS",
    "LITERAL_CLASSES",
    "LITERAL_TYPES",
    "LITERALS",
    "NULLITY",
    "Arity",
    "Field",
    "Kinds",
    "Operator",
    "Reference",
    "Schema",
    "Table",
    "Type",
    "TypeClass",
    "classify",
    "column_name",
    "comparisons",
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
