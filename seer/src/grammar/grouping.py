"""GROUP BY and HAVING.

    <grouping> := GROUP BY <column> [, <column>]* [HAVING <filters>]

The keys are columns of the closed relation, each grouped once however it is
spelled. HAVING is the condition grammar of `conditions.py` over a different
domain: on the left a grouped column or an aggregate over any column, on the
right a literal or a grouped column of the same class.

Whether the query may end after its keys is the virtual table's question, and
it is asked where the query ends, not here.
"""

from __future__ import annotations

from ..context import Context
from ..model import FUNCTIONS, Function
from ..query import Operand
from ..runtime import Selector, Thunk
from .combinators import branch, comma, dynamic, exp, keyword, lat, ws
from .conditions import Continuation, Domain, filters
from .selectors import select, step
from .tokens import LPAREN, NESTING_LIMIT, RPAREN

_enter_grouping: Selector = step(lambda ctx: ctx.query.enter_grouping())
_enter_having: Selector = step(lambda ctx: ctx.query.enter_having())
_select_key: Selector = select(lambda ctx, matched: ctx.query.use_group_key(matched))

def keys(next: Thunk) -> Thunk:
    """A comma separated list of columns, none of them grouped twice."""

    fork: Thunk = branch([
        next,
        Thunk.deferred(lambda: comma(keys(next))),
    ])

    return dynamic(lambda ctx: [
        lat(operand.text, _select_key, fork) for operand in ctx.query.refinement.group_candidates()
    ])

def _aggregate(function: Function, then: Continuation) -> Thunk:
    """`FN(<column>)` over every column `function` accepts, continued by `then`."""

    def build(ctx: Context) -> list[Thunk]:
        arguments: list[Thunk] = [
            lat(operand.text, None, exp(RPAREN, None, then(operand.aggregated(function))))
            for operand in ctx.query.refinement.aggregable(function)
        ]

        if function.star:
            arguments.append(lat("*", None, exp(RPAREN, None, then(Operand.star(function)))))

        return arguments

    return lat(function.name, None, exp(LPAREN, None, dynamic(build)))

def _having_left(then: Continuation) -> Thunk:
    grouped: Thunk = dynamic(lambda ctx: [
        lat(operand.text, None, then(operand)) for operand in ctx.query.refinement.grouped()
    ])

    return branch([grouped, *(_aggregate(function, then) for function in FUNCTIONS)])

HAVING: Domain = Domain(
    left=_having_left,
    right=lambda ctx, kind: ctx.query.refinement.grouped(kind),
    record=lambda ctx, text: ctx.query.use_filter(text),
)

def having_clause(next: Thunk) -> Thunk:
    return keyword("HAVING", _enter_having, ws(filters(HAVING, next, NESTING_LIMIT)))

def grouping_clause(next: Thunk) -> Thunk:
    """An optional `GROUP BY <keys> [HAVING <filters>]` before `next`."""

    grouped: Thunk = keys(branch([next, having_clause(next)]))

    return branch([
        next,
        keyword("GROUP", None, ws(lat("BY", _enter_grouping, ws(grouped)))),
    ])
