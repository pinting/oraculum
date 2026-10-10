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
# for the grammar to stay unambiguous; the rest are here because a statement
# has to run where it is sent, and a dialect refuses an unquoted alias that
# spells one of its keywords - SQLite `NOTHING`, PostgreSQL `USER`. So the set
# is every keyword SQLite knows and every word PostgreSQL reserves, and the
# grammar's own are among them. Keywords are case insensitive, so every
# spelling of one is excluded at the point of use - see `query.names`.
SQLITE_KEYWORDS: frozenset[str] = frozenset({
    "ABORT", "ACTION", "ADD", "AFTER", "ALL", "ALTER", "ALWAYS", "ANALYZE",
    "AND", "AS", "ASC", "ATTACH", "AUTOINCREMENT", "BEFORE", "BEGIN",
    "BETWEEN", "BY", "CASCADE", "CASE", "CAST", "CHECK", "COLLATE", "COLUMN",
    "COMMIT", "CONFLICT", "CONSTRAINT", "CREATE", "CROSS", "CURRENT",
    "CURRENT_DATE", "CURRENT_TIME", "CURRENT_TIMESTAMP", "DATABASE",
    "DEFAULT", "DEFERRABLE", "DEFERRED", "DELETE", "DESC", "DETACH",
    "DISTINCT", "DO", "DROP", "EACH", "ELSE", "END", "ESCAPE", "EXCEPT",
    "EXCLUDE", "EXCLUSIVE", "EXISTS", "EXPLAIN", "FAIL", "FILTER", "FIRST",
    "FOLLOWING", "FOR", "FOREIGN", "FROM", "FULL", "GENERATED", "GLOB",
    "GROUP", "GROUPS", "HAVING", "IF", "IGNORE", "IMMEDIATE", "IN", "INDEX",
    "INDEXED", "INITIALLY", "INNER", "INSERT", "INSTEAD", "INTERSECT",
    "INTO", "IS", "ISNULL", "JOIN", "KEY", "LAST", "LEFT", "LIKE", "LIMIT",
    "MATCH", "MATERIALIZED", "NATURAL", "NO", "NOT", "NOTHING", "NOTNULL",
    "NULL", "NULLS", "OF", "OFFSET", "ON", "OR", "ORDER", "OTHERS", "OUTER",
    "OVER", "PARTITION", "PLAN", "PRAGMA", "PRECEDING", "PRIMARY", "QUERY",
    "RAISE", "RANGE", "RECURSIVE", "REFERENCES", "REGEXP", "REINDEX",
    "RELEASE", "RENAME", "REPLACE", "RESTRICT", "RETURNING", "RIGHT",
    "ROLLBACK", "ROW", "ROWS", "SAVEPOINT", "SELECT", "SET", "TABLE",
    "TEMP", "TEMPORARY", "THEN", "TIES", "TO", "TRANSACTION", "TRIGGER",
    "UNBOUNDED", "UNION", "UNIQUE", "UPDATE", "USING", "VACUUM", "VALUES",
    "VIEW", "VIRTUAL", "WHEN", "WHERE", "WINDOW", "WITH", "WITHOUT",
})

POSTGRES_RESERVED: frozenset[str] = frozenset({
    "ALL", "ANALYSE", "ANALYZE", "AND", "ANY", "ARRAY", "AS", "ASC",
    "ASYMMETRIC", "AUTHORIZATION", "BINARY", "BOTH", "CASE", "CAST",
    "CHECK", "COLLATE", "COLLATION", "COLUMN", "CONCURRENTLY", "CONSTRAINT",
    "CREATE", "CROSS", "CURRENT_CATALOG", "CURRENT_DATE", "CURRENT_ROLE",
    "CURRENT_SCHEMA", "CURRENT_TIME", "CURRENT_TIMESTAMP", "CURRENT_USER",
    "DEFAULT", "DEFERRABLE", "DESC", "DISTINCT", "DO", "ELSE", "END",
    "EXCEPT", "FALSE", "FETCH", "FOR", "FOREIGN", "FREEZE", "FROM", "FULL",
    "GRANT", "GROUP", "HAVING", "ILIKE", "IN", "INITIALLY", "INNER",
    "INTERSECT", "INTO", "IS", "ISNULL", "JOIN", "LATERAL", "LEADING",
    "LEFT", "LIKE", "LIMIT", "LOCALTIME", "LOCALTIMESTAMP", "NATURAL", "NOT",
    "NOTNULL", "NULL", "OFFSET", "ON", "ONLY", "OR", "ORDER", "OUTER",
    "OVERLAPS", "PLACING", "PRIMARY", "REFERENCES", "RETURNING", "RIGHT",
    "SELECT", "SESSION_USER", "SIMILAR", "SOME", "SYMMETRIC", "SYSTEM_USER",
    "TABLE", "TABLESAMPLE", "THEN", "TO", "TRAILING", "TRUE", "UNION",
    "UNIQUE", "USER", "USING", "VARIADIC", "VERBOSE", "WHEN", "WHERE",
    "WINDOW", "WITH",
})

KEYWORDS: frozenset[str] = SQLITE_KEYWORDS | POSTGRES_RESERVED

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
