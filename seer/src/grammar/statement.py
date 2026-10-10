"""The statement, end to end.

    <statement>  := [WITH [RECURSIVE] <definition> [, <definition>]*] <query> ;
    <definition> := <name> [( <name> [, <name>]* )] AS ( <query> )
    <query>      := <member> [<set operator> <member>]* [ORDER BY ...] [LIMIT ...]
    <member>     := SELECT [DISTINCT] <items> FROM <entry> [, <entry>]*
                    [WHERE <filters>] [GROUP BY <keys> [HAVING <filters>]]

A definition and the main query are the same `<query>`, ended differently: a
definition by its closing bracket, which pushes it onto the stack, the main
query by the terminator. Either is only offered where the virtual table says
the query may end, which is where the rules that span clauses - GROUP BY owed
by an aggregating projection, values it has to cover - are enforced.

A compound is its members one after another, each ended by the set operator
that opens the next; ORDER BY and LIMIT come after the last, and apply to all
of them.
"""

from __future__ import annotations

from ..query import SET_OPERATORS, SetOperator
from ..runtime import Selector, Thunk
from .combinators import branch, comma, exp, guard, keyword, lat, name, ws
from .filter import where_clause
from .grouping import grouping_clause
from .presentation import presentation
from .projection import projection
from .selectors import select, step
from .source import from_clause
from .tokens import LPAREN, RPAREN, TERMINATOR

_begin_main: Selector = step(lambda ctx: ctx.begin_main())
_begin_definition: Selector = select(lambda ctx, matched: ctx.begin_definition(matched))
_name_column: Selector = select(lambda ctx, matched: ctx.name_column(matched))
_open_definition: Selector = step(lambda ctx: ctx.open_definition())
_end_definition: Selector = step(lambda ctx: ctx.end_definition())
_use_recursive: Selector = step(lambda ctx: ctx.use_recursive())
_enter_source: Selector = step(lambda ctx: ctx.query.enter_source())
_close: Selector = step(lambda ctx: ctx.query.close())

def _combine(operator: SetOperator) -> Selector:
    return step(lambda ctx: ctx.combine(operator))

def closing(pattern: str, selector: Selector, next: Thunk) -> Thunk:
    """The token that ends a query, offered only once the query may end."""

    return guard(lambda ctx: ctx.query.can_close(), exp(pattern, selector, next))

def member(after: Thunk) -> Thunk:
    """One member, from its items up to the end of its body, then `after`."""

    tail: Thunk = where_clause(grouping_clause(after))

    return projection(lat("FROM", _enter_source, ws(from_clause(tail))))

def query(end: Thunk) -> Thunk:
    """Everything after the first `SELECT`: members, the presentation, and `end`."""

    def after() -> Thunk:
        return branch([presentation(end), combination])

    following: Thunk = Thunk.deferred(lambda: member(Thunk.deferred(after)))

    combination: Thunk = guard(
        lambda ctx: ctx.query.can_combine(),
        branch([
            keyword(str(operator), _combine(operator), ws(lat("SELECT", None, ws(following))))
            for operator in SET_OPERATORS
        ]),
    )

    return member(Thunk.deferred(after))

def main_query() -> Thunk:
    end: Thunk = closing(TERMINATOR, _close, Thunk.terminal())

    return lat("SELECT", _begin_main, ws(query(end)))

def definitions(next: Thunk) -> Thunk:
    """`<name> [(<columns>)] AS ( <query> )`, then another definition or `next`."""

    after: Thunk = branch([
        Thunk.deferred(lambda: comma(definitions(next))),
        ws(next),
    ])

    body: Thunk = lat("SELECT", _open_definition, ws(query(closing(RPAREN, _end_definition, after))))
    opening: Thunk = keyword("AS", None, ws(exp(LPAREN, None, body)))

    def columns() -> Thunk:
        listed: Thunk = branch([
            exp(RPAREN, None, opening),
            Thunk.deferred(lambda: comma(columns())),
        ])

        return name(lambda ctx: ctx.get_column_reserved_names(), _name_column, listed)

    return name(
        lambda ctx: ctx.get_reserved_names(),
        _begin_definition,
        branch([opening, exp(LPAREN, None, Thunk.deferred(columns))]),
    )

def root() -> Thunk:
    main: Thunk = main_query()
    listed: Thunk = definitions(main)

    return branch([
        main,
        lat("WITH", None, ws(branch([
            listed,
            lat("RECURSIVE", _use_recursive, ws(listed)),
        ]))),
    ])
