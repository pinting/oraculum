"""The WHERE clause: conditions over the relation the FROM clause produced.

Its keyword closes the FROM clause, and every operand afterwards is a value
of that one relation - a column, written the way SQL's ambiguity rule allows,
or a scalar function over columns - or, in a subquery, a column of a query
around it, qualified.
"""

from __future__ import annotations

from ..runtime import Thunk
from .combinators import branch, keyword, ws
from .conditions import Continuation, Domain, Right, comparable, filters
from .operands import operands
from .selectors import step
from .tokens import EXPRESSION_DEPTH, NESTING_LIMIT

_right: Right = lambda ctx, kind: ctx.query.condition_operands(kind)

def _left(then: Continuation) -> Thunk:
    columns = lambda ctx: ctx.query.condition_operands()

    return operands(
        comparable(_right, columns), columns, None, lambda operand: (None, then(operand)), EXPRESSION_DEPTH
    )

WHERE: Domain = Domain(
    left=_left,
    right=_right,
    record=lambda ctx, text: ctx.query.use_filter(text),
)

_enter_filter = step(lambda ctx: ctx.query.enter_filter())

def where_clause(next: Thunk) -> Thunk:
    """An optional `WHERE <filters>` between the FROM clause and what follows."""

    return branch([
        next,
        keyword("WHERE", _enter_filter, ws(filters(WHERE, next, NESTING_LIMIT))),
    ])
