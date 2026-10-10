"""ORDER BY and LIMIT, after the body of a query.

    <presentation> := [ORDER BY <key> [ASC | DESC] [, ...]*] [LIMIT <count> [OFFSET <count>]]
    <key>          := <output> | <operand> | <aggregate>

What a key may be is the presentation part's question (`query.presentation`):
an output name, a value of the relation or a function over one, an aggregate -
whichever the result allows. Each is offered only once the body is complete,
which is the virtual table's to say.
"""

from __future__ import annotations

from ..query import Operand
from ..runtime import Selector, Thunk
from ..state import Clause
from .combinators import branch, comma, exp, guard, keyword, lat, ws
from .operands import aggregates, offers, operands
from .selectors import select, step
from .tokens import COUNT, EXPRESSION_DEPTH

_enter_ordering: Selector = step(lambda ctx: ctx.query.enter_ordering())
_enter_limiting: Selector = step(lambda ctx: ctx.query.enter_limiting())
_use_limit: Selector = select(lambda ctx, matched: ctx.query.use_limit(matched))
_use_offset: Selector = select(lambda ctx, matched: ctx.query.use_offset(matched))

def _sort(key: Operand) -> Selector:
    return select(lambda ctx, _matched: ctx.query.use_order_key(key))

def _direct(direction: str) -> Selector:
    return select(lambda ctx, _matched: ctx.query.use_order_direction(direction))

def order_keys(next: Thunk) -> Thunk:
    """A comma separated list of sort keys, each with an optional direction."""

    candidates = lambda ctx: ctx.query.presentation.candidates()
    arguments = lambda ctx: ctx.query.presentation.arguments()
    more = offers(candidates, arguments, None, EXPRESSION_DEPTH)

    # Another key is only offered while something is left to sort by: an
    # aggregate always is, a value of the result only until each is used.
    fork: Thunk = branch([
        next,
        guard(
            lambda ctx: ctx.query.presentation.aggregates or more(ctx),
            Thunk.deferred(lambda: comma(order_keys(next))),
        ),
    ])
    directed: Thunk = branch([
        fork,
        ws(branch([lat(direction, _direct(direction), fork) for direction in ("ASC", "DESC")])),
    ])
    then = lambda key: (_sort(key), directed)

    return branch([
        operands(candidates, arguments, None, then, EXPRESSION_DEPTH),
        guard(
            lambda ctx: ctx.query.presentation.aggregates,
            aggregates(lambda ctx: ctx.query.refinement.operands(), None, then, EXPRESSION_DEPTH),
        ),
    ])

def limit_clause(next: Thunk) -> Thunk:
    """`LIMIT <count> [OFFSET <count>]`."""

    offset: Thunk = keyword("OFFSET", None, ws(exp(COUNT, _use_offset, next)))

    return guard(
        lambda ctx: ctx.query.can_enter(Clause.LIMITING),
        keyword("LIMIT", _enter_limiting, ws(exp(COUNT, _use_limit, branch([next, offset])))),
    )

def presentation(next: Thunk) -> Thunk:
    """An optional ORDER BY, an optional LIMIT, then `next`."""

    limited: Thunk = branch([next, limit_clause(next)])

    return branch([
        limited,
        guard(
            lambda ctx: ctx.query.can_order(),
            keyword("ORDER", None, ws(lat("BY", _enter_ordering, ws(order_keys(limited))))),
        ),
    ])
