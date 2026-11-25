"""Validating completed legal queries with `sqlglot` in PostgreSQL dialect.

Unlike SQLite, PostgreSQL rejects ungrouped columns in aggregate queries and
silent cross-class comparisons. This validator parses each query under the
PostgreSQL dialect, qualifies every table/column/CTE against the schema,
annotates expression types, and checks strict comparison compatibility and
GROUP BY coverage on the resulting AST.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp, optimizer
from sqlglot.optimizer.scope import Scope, build_scope
from sqlglot.schema import MappingSchema

from .base import Validation

_BINARY_TYPES = tuple(
    t
    for name in ("BINARY", "VARBINARY", "BLOB", "BYTEA")
    if (t := getattr(exp.DataType.Type, name, None)) is not None
)


def _schema_from_ddl(ddl: str) -> MappingSchema:
    tables: dict[str, dict[str, str]] = {}

    for statement in sqlglot.parse(ddl):
        if not isinstance(statement, exp.Create) or statement.args.get("kind") != "TABLE":
            continue

        definition = statement.this
        if definition is None:
            continue

        table_name: str = definition.this.name
        tables[table_name] = {
            column.name: column.args["kind"].sql(dialect="postgres")
            for column in definition.expressions
            if isinstance(column, exp.ColumnDef) and column.args.get("kind") is not None
        }

    return MappingSchema(tables, dialect="postgres")


def _kind_group(node: exp.Expression) -> str | None:
    if isinstance(node, exp.Literal) and node.is_string:
        return "string_literal"

    dtype = node.type
    if not isinstance(dtype, exp.DataType):
        return None

    tag = dtype.this
    if tag in exp.DataType.NUMERIC_TYPES:
        return "numeric"
    if tag in exp.DataType.TEXT_TYPES:
        return "text"
    if tag in exp.DataType.TEMPORAL_TYPES:
        return "temporal"
    if tag == exp.DataType.Type.BOOLEAN:
        return "boolean"
    if tag in _BINARY_TYPES:
        return "binary"
    return None


def _compatible(left: exp.Expression, right: exp.Expression) -> bool:
    left_kind = _kind_group(left)
    right_kind = _kind_group(right)

    if left_kind is None or right_kind is None or left_kind == right_kind:
        return True

    if "string_literal" in (left_kind, right_kind):
        other = right_kind if left_kind == "string_literal" else left_kind
        return other in ("text", "temporal")

    return False


def _check_comparisons(tree: exp.Expression) -> str | None:
    for node in tree.walk():
        if isinstance(node, (exp.EQ, exp.NEQ, exp.LT, exp.LTE, exp.GT, exp.GTE)):
            if not _compatible(node.left, node.right):
                return f"incompatible comparison: {node.sql(dialect='postgres')}"
        elif isinstance(node, exp.Between):
            low = node.args.get("low")
            high = node.args.get("high")
            if (low is not None and not _compatible(node.this, low)) or (
                high is not None and not _compatible(node.this, high)
            ):
                return f"incompatible BETWEEN: {node.sql(dialect='postgres')}"
        elif isinstance(node, exp.In) and node.expressions:
            for item in node.expressions:
                if not _compatible(node.this, item):
                    return f"incompatible IN: {node.sql(dialect='postgres')}"
    return None


def _has_aggregate(node: exp.Expression) -> bool:
    if isinstance(node, (exp.Select, exp.Subquery, exp.Window)):
        return False
    if isinstance(node, exp.AggFunc):
        return True
    return any(_has_aggregate(child) for child in node.iter_expressions())


def _check_grouped(node: exp.Expression, grouped: set[str], local_sources: set[str]) -> str | None:
    if isinstance(node, exp.Subquery):
        return None
    if isinstance(node, exp.Alias):
        return _check_grouped(node.this, grouped, local_sources)
    if node.sql(dialect="postgres") in grouped:
        return None
    if isinstance(node, exp.AggFunc):
        return None

    if isinstance(node, exp.Window):
        for part in node.args.get("partition_by") or ():
            if (error := _check_grouped(part, grouped, local_sources)) is not None:
                return error
        order = node.args.get("order")
        if order is not None:
            for item in order.expressions:
                if (error := _check_grouped(item.this, grouped, local_sources)) is not None:
                    return error
        if isinstance(node.this, exp.AggFunc):
            for child in node.this.iter_expressions():
                if (error := _check_grouped(child, grouped, local_sources)) is not None:
                    return error
        return None

    if isinstance(node, exp.Column):
        if node.table and node.table not in local_sources:
            return None
        return f"ungrouped column: {node.sql(dialect='postgres')}"

    for child in node.iter_expressions():
        if (error := _check_grouped(child, grouped, local_sources)) is not None:
            return error
    return None


def _check_scope_grouping(scope: Scope) -> str | None:
    select = scope.expression
    if not isinstance(select, exp.Select):
        return None

    group = select.args.get("group")
    having = select.args.get("having")
    is_aggregated = (
        group is not None
        or any(_has_aggregate(expr) for expr in select.expressions)
        or (having is not None and _has_aggregate(having.this))
    )
    if not is_aggregated:
        return None

    grouped: set[str] = {expr.sql(dialect="postgres") for expr in (group.expressions if group else ())}
    local_sources: set[str] = set(scope.sources)
    output_aliases: dict[str, exp.Expression] = {
        expr.alias: expr.this for expr in select.expressions if isinstance(expr, exp.Alias)
    }

    for expr in select.expressions:
        if (error := _check_grouped(expr, grouped, local_sources)) is not None:
            return error

    if having is not None:
        if (error := _check_grouped(having.this, grouped, local_sources)) is not None:
            return error

    order = select.args.get("order")
    if order is not None:
        for item in order.expressions:
            target = item.this
            if isinstance(target, exp.Column) and not target.table and target.name in output_aliases:
                target = output_aliases[target.name]
            if (error := _check_grouped(target, grouped, local_sources)) is not None:
                return error

    return None


class SqlglotValidator:
    """Validates completed SQL queries via `sqlglot` in PostgreSQL mode."""

    name: str = "sqlglot"
    __slots__ = ("_schema",)

    def __init__(self, schema: str) -> None:
        self._schema: MappingSchema = _schema_from_ddl(schema)

    def validate(self, query: str) -> Validation:
        """Parse, qualify, type-check, and check grouping for `query`."""

        try:
            tree = sqlglot.parse_one(query, read="postgres")
            tree = optimizer.qualify.qualify(tree, schema=self._schema, dialect="postgres")
            tree = optimizer.annotate_types.annotate_types(tree, schema=self._schema, dialect="postgres")
        except Exception as error:
            return Validation(self.name, error=str(error))

        if (error := _check_comparisons(tree)) is not None:
            return Validation(self.name, error=error)

        root_scope = build_scope(tree)
        if root_scope is not None:
            for scope in root_scope.traverse():
                if (error := _check_scope_grouping(scope)) is not None:
                    return Validation(self.name, error=error)

        return Validation(self.name)

    def close(self) -> None:
        return None
