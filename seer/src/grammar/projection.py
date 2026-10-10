"""The projection: `<item> [, <item>]*`.

    <item>       := <column ref> | <aggregate> [AS <name>]
    <aggregate>  := COUNT "(" "*" ")" | <function> "(" <column ref> ")"
    <column ref> := <column> | <alias>.<column>

The column lattices are read off the query, so a name drops out the moment
nothing that could supply it is left - and inside a function, the moment
nothing could supply it with a type the function accepts.
"""

from __future__ import annotations

from typing import Callable

from ..context import Context
from ..model import FUNCTIONS, Function
from ..query import Exclusion, NameUse
from ..runtime import Selector, Thunk
from .combinators import branch, comma, dot, dynamic, exp, guard, keyword, lat, name, ws
from .selectors import select
from .tokens import LPAREN, RPAREN

Columns = Callable[[Context], list[str]]

_open_qualifier: Selector = select(lambda ctx, matched: ctx.query.open_qualifier(matched))
_select_column: Selector = select(lambda ctx, matched: ctx.query.use_column(matched))
_name_item: Selector = select(lambda ctx, matched: ctx.query.name_item(matched))

def _select_argument(function: Function) -> Selector:
    return select(lambda ctx, matched: ctx.query.use_aggregate(function, matched))

def _select_star(function: Function) -> Selector:
    return select(lambda ctx, _matched: ctx.query.use_aggregate(function, None))

def reserved(use: NameUse) -> Callable[[Context], Exclusion]:
    return lambda ctx: ctx.query.selection.reserved(use)

def column_ref(columns: Columns, selector: Selector, next: Thunk) -> Thunk:
    """A column bare, or `<alias>.<column>`, which opens the alias first."""

    bare: Thunk = dynamic(lambda ctx: [lat(column, selector, next) for column in columns(ctx)])
    qualified: Thunk = name(reserved(NameUse.QUALIFIER), _open_qualifier, dot(bare))

    return branch([qualified, bare])

def naming(next: Thunk) -> Thunk:
    """An optional `AS <name>` after an aggregate, where the query allows none."""

    return branch([
        guard(lambda ctx: ctx.query.selection.can_end_item(), next),
        keyword("AS", None, ws(name(reserved(NameUse.OUTPUT), _name_item, next))),
    ])

def aggregate(function: Function, next: Thunk) -> Thunk:
    """`FN(<column ref>)`, or `FN(*)` for a function that takes it."""

    closing: Thunk = exp(RPAREN, None, naming(next))

    arguments: list[Thunk] = [
        column_ref(lambda ctx: ctx.query.selection.arguments(function), _select_argument(function), closing),
    ]

    if function.star:
        arguments.append(lat("*", _select_star(function), closing))

    return lat(function.name, None, exp(LPAREN, None, branch(arguments)))

def items(next: Thunk) -> Thunk:
    """A comma separated item list."""

    fork: Thunk = branch([
        next,
        Thunk.deferred(lambda: comma(items(next))),
    ])

    return branch([
        column_ref(lambda ctx: ctx.query.selection.columns(), _select_column, fork),
        *(aggregate(function, fork) for function in FUNCTIONS),
    ])
