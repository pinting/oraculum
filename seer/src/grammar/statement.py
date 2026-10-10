"""The statement, end to end.

    <statement>  := [WITH <definition> [, <definition>]*] <select> ;
    <definition> := <name> AS ( <select> )
    <select>     := SELECT <items> FROM <entry> [, <entry>]*
                    [WHERE <filters>] [GROUP BY <keys> [HAVING <filters>]]

A definition and the main query are the same `<select>`, ended differently: a
definition by its closing bracket, which pushes it onto the stack, the main
query by the terminator. Either is only offered where the virtual table says
the query may end, which is the one place the rules that span clauses - GROUP
BY owed by a mixed projection, plain columns it has to cover - are enforced.
"""

from __future__ import annotations

from ..runtime import Selector, Thunk
from .combinators import branch, comma, exp, guard, lat, name, ws
from .filter import where_clause
from .grouping import grouping_clause
from .projection import items
from .selectors import select, step
from .source import from_clause
from .tokens import LPAREN, RPAREN, TERMINATOR

_begin_main: Selector = step(lambda ctx: ctx.begin_main())
_begin_definition: Selector = select(lambda ctx, matched: ctx.begin_definition(matched))
_end_definition: Selector = step(lambda ctx: ctx.end_definition())
_enter_source: Selector = step(lambda ctx: ctx.query.enter_source())
_close: Selector = step(lambda ctx: ctx.query.close())

def closing(pattern: str, selector: Selector, next: Thunk) -> Thunk:
    """The token that ends a query, offered only once the query may end."""

    return guard(lambda ctx: ctx.query.can_close(), exp(pattern, selector, next))

def select_body(end: Thunk) -> Thunk:
    """Everything after `SELECT`, up to and including what ends the query."""

    tail: Thunk = where_clause(grouping_clause(end))

    return items(ws(lat("FROM", _enter_source, ws(from_clause(tail)))))

def main_query() -> Thunk:
    end: Thunk = closing(TERMINATOR, _close, Thunk.terminal())

    return lat("SELECT", _begin_main, ws(select_body(end)))

def definitions(next: Thunk) -> Thunk:
    """`<name> AS ( <select> )`, then another definition or `next`."""

    after: Thunk = branch([
        Thunk.deferred(lambda: comma(definitions(next))),
        ws(next),
    ])

    body: Thunk = lat("SELECT", None, ws(select_body(closing(RPAREN, _end_definition, after))))

    return name(
        lambda ctx: ctx.get_reserved_names(),
        _begin_definition,
        ws(lat("AS", None, ws(exp(LPAREN, None, body)))),
    )

def root() -> Thunk:
    main: Thunk = main_query()

    return branch([
        main,
        lat("WITH", None, ws(definitions(main))),
    ])
