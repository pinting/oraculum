"""The FROM clause, which is resolved by walking the foreign key graph.

    <entry> := <table> [AS <alias>] [<join>]*
    <join>  := <join type> <table> [AS <alias>] ON <column> = <column>

Two loops shape it: the outer one over entries is `from_entry` plus `finish`,
the inner one over joins is `joins`.
"""

from __future__ import annotations

from ..context import Context
from ..model import unqualify
from ..resolution import JoinType, Neighbor
from ..runtime import Selector, Thunk
from .combinators import comma, dynamic, lat, ws
from .selectors import select

def _select_table(node: str) -> Selector:
    return select(lambda ctx, _matched: ctx.query.use_table(node))

def _select_join(neighbor: Neighbor, join_type: JoinType) -> Selector:
    return select(lambda ctx, _matched: ctx.query.join_table(neighbor, join_type))

def node_name(node: str, selector: Selector, next: Thunk) -> Thunk:
    """Emit a node as `table` or `table AS alias`, selecting on the last token."""

    table, alias = unqualify(node)

    if not alias:
        return lat(table, selector, next)

    tail: Thunk = lat(alias, selector, next)
    tail = ws(tail)
    tail = lat("AS", None, tail)
    tail = ws(tail)

    return lat(table, None, tail)

def from_entry(next: Thunk) -> Thunk:
    """One FROM entry: a table the query may open with, then any joins off it."""

    return dynamic(lambda ctx: [
        node_name(node, _select_table(node), Thunk.deferred(lambda: joins(next)))
        for node in ctx.query.sources.entries()
    ])

def join_clause(neighbor: Neighbor, join_type: JoinType, next: Thunk) -> Thunk:
    """`<join type> <table> [AS <alias>] ON <column> = <column>`.

    The selector sits on the last token, so the join is only committed once the
    whole clause has been written.
    """

    tail: Thunk = lat(neighbor.dst_field, _select_join(neighbor, join_type), next)
    tail = ws(tail)
    tail = lat("=", None, tail)
    tail = ws(tail)
    tail = lat(neighbor.src_field, None, tail)
    tail = ws(tail)
    tail = lat("ON", None, tail)
    tail = ws(tail)
    tail = node_name(neighbor.table, None, tail)
    tail = ws(tail)

    return lat(str(join_type), None, tail)

def joins(next: Thunk) -> Thunk:
    """Zero or more JOINs off the current entry, then finish it."""

    def build(ctx: Context) -> list[Thunk]:
        options: list[Thunk] = [finish(next)]

        for neighbor in ctx.query.sources.neighbors():
            for join_type in ctx.query.sources.join_types():
                options.append(ws(join_clause(
                    neighbor,
                    join_type,
                    Thunk.deferred(lambda: joins(next)),
                )))

        return options

    return dynamic(build)

def finish(next: Thunk) -> Thunk:
    """End the entry: continue the statement, or start another FROM entry."""

    return dynamic(lambda ctx: [next] if ctx.query.sources.is_satisfied() else [comma(from_entry(next))])

def from_clause(next: Thunk) -> Thunk:
    return from_entry(next)
