"""A scalar subquery as a value: `(SELECT MAX(id) FROM posts)`.

It is written where its value stands, before the FROM clause of the query
around it exists, so it reads nothing of that query: it is the same value for
every row, which grouping counts as a constant. Its class is whatever its one
item turns out to be, within what the position allows, and is only known once
it closes - so the value is built then, from the result it hands back.
"""

from __future__ import annotations

from ...query import Scalar, Subquery
from ...runtime import Thunk
from ..combinators import dynamic, exp
from ..subquery import subquery
from ..tokens import LPAREN
from .position import Position, Then

def scalar_subquery(position: Position, then: Then) -> Thunk:
    resume: Thunk = dynamic(lambda ctx: [
        then(Subquery(ctx.finished.result()[0].field, ctx.serial))
    ])

    return exp(LPAREN, None, subquery(Scalar(position.kinds), resume))
