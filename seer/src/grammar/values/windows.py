"""Windows: `OVER ([PARTITION BY ...] [ORDER BY ...])`.

A window's keys are plain columns of the row - nothing nested, nothing
aggregated - and a ranking function demands the ORDER BY, which ranking means
nothing without.
"""

from __future__ import annotations

from typing import Callable

from ...query import Direction, Expr
from ...runtime import Thunk
from ..combinators import branch, comma, exp, keyword, lat, ws
from ..tokens import RPAREN, SPACED_LPAREN
from .leaves import column_ref
from .position import Position

WindowThen = Callable[[tuple[Expr, ...], tuple[tuple[Expr, Direction], ...]], Thunk]

# What a window's keys are: columns, of any class, and nothing nested.
KEY: Position = Position(depth=0, aggregates=False, windows=False)

def over(ordered: bool, then: WindowThen) -> Thunk:
    """` OVER ([PARTITION BY ...] [ORDER BY ...])`; `ordered` demands the ORDER BY."""

    def closing(partition: tuple[Expr, ...], order: tuple[tuple[Expr, Direction], ...]) -> Thunk:
        return exp(RPAREN, None, then(partition, order))

    def ordering(partition: tuple[Expr, ...]) -> Thunk:
        def keys(written: tuple[tuple[Expr, Direction], ...]) -> Thunk:
            def directed(key: tuple[Expr, Direction]) -> Thunk:
                done: tuple[tuple[Expr, Direction], ...] = written + (key,)

                return branch([closing(partition, done), comma(Thunk.deferred(lambda: keys(done)))])

            def after(column: Expr) -> Thunk:
                return branch([
                    directed((column, "")),
                    ws(branch([
                        lat(direction, None, directed((column, direction))) for direction in ("ASC", "DESC")
                    ])),
                ])

            return column_ref(KEY, after)

        return lat("ORDER", None, ws(lat("BY", None, ws(keys(())))))

    def partitioning() -> Thunk:
        def keys(written: tuple[Expr, ...]) -> Thunk:
            def after(column: Expr) -> Thunk:
                done: tuple[Expr, ...] = written + (column,)
                options: list[Thunk] = [ws(Thunk.deferred(lambda: ordering(done)))]

                if not ordered:
                    options.append(closing(done, ()))

                return branch(options + [comma(Thunk.deferred(lambda: keys(done)))])

            return column_ref(KEY, after)

        return lat("PARTITION", None, ws(lat("BY", None, ws(keys(())))))

    spec: list[Thunk] = [Thunk.deferred(partitioning), Thunk.deferred(lambda: ordering(()))]

    if not ordered:
        spec.append(closing((), ()))

    return keyword("OVER", None, exp(SPACED_LPAREN, None, branch(spec)))
