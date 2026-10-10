"""Values: a term, and the arithmetic that may extend it."""

from __future__ import annotations

from ...context import Context
from ...model import AGGREGATES, NUMERIC, RANKINGS, SCALARS, TypeClass
from ...query import Arithmetic, Column, Expr, narrowing
from ...runtime import Thunk
from ..combinators import branch, dynamic, exp
from ..tokens import ARITHMETIC
from .calls import aggregate, ranking, scalar
from .cases import case
from .subqueries import scalar_subquery
from .leaves import column_ref, literal
from .narrow import can_narrow, narrower
from .position import Need, Position, Then

def term(position: Position, then: Then) -> Thunk:
    """One value, without arithmetic around it."""

    options: list[Thunk | None] = []

    # A column is a value of the row, and a literal holds no aggregate.
    if position.reads_row:
        options.append(column_ref(position, then))

    if position.need is not Need.AGGREGATE:
        options.append(literal(position, then))

    if position.depth > 0:
        options.extend(scalar(function, position, then) for function in SCALARS)

        if position.aggregates:
            options.extend(aggregate(function, position, then) for function in AGGREGATES)

        if position.windows and position.reads_row:
            options.extend(ranking(function, position, then) for function in RANKINGS)

        if position.need is not Need.AGGREGATE:
            options.append(case(position, then))

        # A subquery is a constant to the row it stands in, so it may stand
        # wherever a constant may - but holds no aggregate of this query.
        if position.aggregates and position.need is not Need.AGGREGATE:
            options.append(scalar_subquery(position, then))

    return branch([option for option in options if option is not None])

def extend(position: Position, expr: Expr, then: Then) -> Thunk:
    """`expr`, or `expr <operator> <term>` and onwards, where it may be numeric."""

    if not position.allows(TypeClass.NUMERIC):
        return then(expr)

    def build(ctx: Context) -> list[Thunk]:
        options: list[Thunk] = [then(expr)]
        columns: tuple[Column, ...] | None = narrowing(expr, NUMERIC)

        if not can_narrow(ctx, columns, NUMERIC):
            return options

        assert columns is not None

        for symbol, pattern in ARITHMETIC:
            def right(symbol: str = symbol) -> Thunk:
                return term(
                    position.beside(),
                    lambda operand: extend(position, Arithmetic(expr, symbol, operand), then),
                )

            options.append(exp(pattern, narrower(columns, NUMERIC), Thunk.deferred(right)))

        return options

    return dynamic(build)

def value(position: Position, then: Then) -> Thunk:
    """A value at `position`, handed whole to `then`."""

    return term(position, lambda expr: extend(position, expr, then))
