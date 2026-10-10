"""How things are named: the keywords, and the spelling of a FROM node.

A FROM node is a table as the clause places it: `"users"` bare, or `"users u"`
once an alias renames it. That one string is how the scopes, the join graph and
the virtual table all refer to a source, and the functions here turn it into
each of the spellings SQL needs.
"""

from __future__ import annotations

# Words an identifier must not spell to be usable as an alias.
#
# Only the keywords the generated language can actually emit have to be here
# for the grammar to stay unambiguous; the rest are listed because an alias
# that shadows a SQL keyword is a bad alias whether or not seer would trip
# over it. Keywords are case insensitive, so every spelling of one is
# excluded at the point of use - see `query.names`.
KEYWORDS: frozenset[str] = frozenset({
    "ALL", "AND", "AS", "ASC", "BETWEEN", "BY", "CASE", "CROSS", "DESC",
    "DISTINCT", "ELSE", "END", "EXISTS", "FROM", "FULL", "GROUP", "HAVING",
    "IN", "INNER", "IS", "JOIN", "LEFT", "LIKE", "LIMIT", "NOT", "NULL",
    "OFFSET", "ON", "OR", "ORDER", "OUTER", "RIGHT", "SELECT", "THEN",
    "UNION", "WHEN", "WHERE", "WITH",
})

def qualify(table: str, alias: str) -> str:
    """`"users u"` for an aliased table, `"users"` for a bare one."""

    if not alias:
        return table

    return f"{table} {alias}"

def unqualify(node: str) -> tuple[str, str]:
    """Split a node name back into `(table, alias)`; alias is `""` if bare."""

    parts: list[str] = node.split()

    if len(parts) == 1:
        return parts[0], ""

    return parts[0], parts[1]

def sql_name(node: str) -> str:
    """How a node is written in a FROM or JOIN clause: `"comments AS cm"`."""

    table, alias = unqualify(node)

    if not alias:
        return table

    return f"{table} AS {alias}"

def reference_name(node: str) -> str:
    """How a node is referred to once it is in the clause: `"c"`, `"users"`.

    These tokens are emitted verbatim, so they have to be valid SQL: an aliased
    node is referenced by its alias and a bare one by its table name. It is the
    qualifier of every column reference the node supplies, which is what an
    `ON` clause and a `WHERE` operand are both written from.
    """

    table, alias = unqualify(node)

    return alias if alias else table

def column_name(qualifier: str, column: str) -> str:
    """`"u.email"` qualified, `"email"` bare."""

    return f"{qualifier}.{column}" if qualifier else column
