"""The WHERE clause: conditions over the relation the FROM clause produced.

Its keyword closes the FROM clause, and every operand afterwards is a column
of that one relation, written the way SQL's ambiguity rule allows.
"""

from __future__ import annotations

from ..runtime import Thunk
from .combinators import branch, dynamic, keyword, lat, ws
from .conditions import Continuation, Domain, filters
from .selectors import step
from .tokens import NESTING_LIMIT

def _columns(then: Continuation) -> Thunk:
    return dynamic(lambda ctx: [
        lat(operand.text, None, then(operand)) for operand in ctx.query.refinement.operands()
    ])

WHERE: Domain = Domain(
    left=_columns,
    right=lambda ctx, kind: ctx.query.refinement.operands(kind),
    record=lambda ctx, text: ctx.query.use_filter(text),
)

_enter_filter = step(lambda ctx: ctx.query.enter_filter())

def where_clause(next: Thunk) -> Thunk:
    """An optional `WHERE <filters>` between the FROM clause and what follows."""

    return branch([
        next,
        keyword("WHERE", _enter_filter, ws(filters(WHERE, next, NESTING_LIMIT))),
    ])
