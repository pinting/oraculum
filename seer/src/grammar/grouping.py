"""GROUP BY and HAVING.

    <grouping> := GROUP BY <key> [, <key>]* [HAVING <filters>]
    <key>      := <column> | FN "(" <key> ")"

A key is a value of the closed relation: a column, grouped once however it is
spelled, or a scalar function over columns, which is a key of its own -
`GROUP BY LOWER(email)` groups the lower cased addresses, and covers the item
`LOWER(email)` but not `email`.

HAVING is the condition grammar of `conditions.py` over a different domain: on
the left a grouped value, a function over grouped values or an aggregate over
any column, on the right a literal or a grouped value of the same class.

Whether the query may end after its keys is the virtual table's question, and
it is asked where the query ends, not here.
"""

from __future__ import annotations

from ..query import Operand
from ..runtime import Selector, Thunk
from ..state import Clause
from .combinators import branch, comma, guard, keyword, lat, ws
from .conditions import Continuation, Domain, filters
from .operands import aggregates, operands
from .selectors import select, step
from .tokens import EXPRESSION_DEPTH, NESTING_LIMIT

_enter_grouping: Selector = step(lambda ctx: ctx.query.enter_grouping())
_enter_having: Selector = step(lambda ctx: ctx.query.enter_having())

def _select_key(key: Operand) -> Selector:
    return select(lambda ctx, _matched: ctx.query.use_group_key(key))

def keys(next: Thunk) -> Thunk:
    """A comma separated list of keys, no column grouped twice."""

    fork: Thunk = branch([
        next,
        Thunk.deferred(lambda: comma(keys(next))),
    ])

    return operands(
        lambda ctx: ctx.query.refinement.group_candidates(),
        lambda ctx: ctx.query.refinement.operands(),
        None,
        lambda key: (_select_key(key), fork),
        EXPRESSION_DEPTH,
    )

def _having_left(then: Continuation) -> Thunk:
    continued = lambda operand: (None, then(operand))
    grouped = lambda ctx: ctx.query.refinement.grouped()

    return branch([
        operands(grouped, grouped, None, continued, EXPRESSION_DEPTH),
        aggregates(lambda ctx: ctx.query.refinement.operands(), None, continued, EXPRESSION_DEPTH),
    ])

HAVING: Domain = Domain(
    left=_having_left,
    right=lambda ctx, kind: ctx.query.refinement.grouped(kind),
    record=lambda ctx, text: ctx.query.use_filter(text),
)

def having_clause(next: Thunk) -> Thunk:
    return guard(
        lambda ctx: ctx.query.can_enter(Clause.HAVING),
        keyword("HAVING", _enter_having, ws(filters(HAVING, next, NESTING_LIMIT))),
    )

def grouping_clause(next: Thunk) -> Thunk:
    """An optional `GROUP BY <keys> [HAVING <filters>]` before `next`."""

    grouped: Thunk = keys(branch([next, having_clause(next)]))

    return branch([
        next,
        guard(
            lambda ctx: ctx.query.can_enter(Clause.GROUPING),
            keyword("GROUP", None, ws(lat("BY", _enter_grouping, ws(grouped)))),
        ),
    ])
