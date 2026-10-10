"""A scalar subquery as a value: `(SELECT MAX(id) FROM posts)`.

It is written where its value stands, before the FROM clause of the query
around it exists, so it reads nothing of that query: it is the same value for
every row, which grouping counts as a constant. Its class is whatever its one
item turns out to be, within what the position allows, and is only known once
it closes - so the value is built then, from the result it hands back.

Its one item has to fold the whole query into one row, so it is only offered
where the position allows a class an aggregate can have.
"""

from __future__ import annotations

from ...model import AGGREGATED
from ...query import Scalar, Subquery
from ...runtime import Thunk
from ..combinators import dynamic
from ..subquery import bracketed
from .position import Position, Then

def scalar_subquery(position: Position, then: Then) -> Thunk | None:
    if position.kinds is not None and not position.kinds & AGGREGATED:
        return None

    resume: Thunk = dynamic(lambda ctx: [
        then(Subquery(ctx.finished.result()[0].field, ctx.serial))
    ])

    return bracketed(Scalar(position.kinds), resume)
