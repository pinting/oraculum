"""Calls: scalar functions, casts, aggregates and ranking functions.

Each emitter answers with `None` where the position does not allow what the
function produces, which is how `LOWER(` is never offered where a number is
wanted. Arguments are values themselves, so this module and `values.py` call
each other; it reads `value` through the module, once both are loaded.
"""

from __future__ import annotations

from ...model import Function, Kinds
from ...query import STAR, Call, Expr, Window
from ...runtime import Thunk
from ..combinators import branch, comma, exp, keyword, lat, ws
from ..tokens import EMPTY_ARGUMENTS, LPAREN, RPAREN
from dataclasses import replace

from . import values
from .position import Need, Position, Then, meet
from .windows import over

def arguments(function: Function, positions: tuple[Position, ...], then: Then, distinct: bool = False) -> Thunk:
    """`<value> [, <value>]* )`, one per position, then `then` of the call."""

    def at(index: int, written: tuple[Expr, ...]) -> Thunk:
        def after(expr: Expr) -> Thunk:
            done: tuple[Expr, ...] = written + (expr,)

            if index + 1 < len(positions):
                return comma(Thunk.deferred(lambda: at(index + 1, done)))

            return exp(RPAREN, None, then(Call(function, done, distinct)))

        return values.value(positions[index], after)

    return at(0, ())

def scalar(function: Function, position: Position, then: Then) -> Thunk | None:
    """`FN(...)` where the position allows what it produces, else `None`."""

    def call(positions: tuple[Position, ...]) -> Thunk:
        return lat(function.name, None, exp(LPAREN, None, Thunk.deferred(
            lambda: arguments(function, positions, then)
        )))

    if function.target is not None:
        return cast(function, position, then)

    def positions(first: Kinds | None, rest: tuple[Kinds | None, ...]) -> tuple[Position, ...]:
        # The first argument carries whatever the position needs.
        return (position.carrying(first),) + tuple(position.within(kinds) for kinds in rest)

    if function.uniform:
        return branch([
            call(positions(frozenset({kind}), tuple(frozenset({kind}) for _ in function.parameters[1:])))
            for kind in position.classes()
        ])

    if function.kind is not None:
        if not position.allows(function.kind):
            return None

        return call(positions(function.accepts(0), function.parameters[1:]))

    first: Kinds | None = meet(function.accepts(0), position.kinds)

    if first is not None and not first:
        return None

    return call(positions(first, function.parameters[1:]))

def cast(function: Function, position: Position, then: Then) -> Thunk | None:
    """`CAST(<value> AS <target>)`."""

    assert function.kind is not None and function.target is not None

    if not position.allows(function.kind):
        return None

    target: str = function.target

    def after(expr: Expr) -> Thunk:
        return keyword("AS", None, ws(lat(target, None, exp(RPAREN, None, then(Call(function, (expr,)))))))

    return lat(function.name, None, exp(LPAREN, None, Thunk.deferred(
        lambda: values.value(position.carrying(function.accepts(0)), after)
    )))

def aggregate(function: Function, position: Position, then: Then) -> Thunk | None:
    """`AGG([DISTINCT] <value>)`, `COUNT(*)`, optionally over a window."""

    if function.kind is not None:
        if not position.allows(function.kind):
            return None

        accepted: Kinds | None = function.accepts(0)
    else:
        accepted = meet(function.accepts(0), position.kinds)

        if accepted is not None and not accepted:
            return None

    # Nothing nests inside an aggregate but plain values of the row: no
    # aggregate, no window - and the row is readable again, whatever the
    # position outside it needed.
    inner: Position = replace(position.within(accepted, aggregates=False), need=Need.ROW)

    def after(call: Call) -> Thunk:
        if not position.windows or call.distinct:
            return then(call)

        return branch([then(call), over(call.function.ordered, lambda p, o: then(Window(call, p, o)))])

    def options() -> Thunk:
        choices: list[Thunk] = [
            values.value(inner, lambda expr: exp(RPAREN, None, after(Call(function, (expr,))))),
        ]

        if function.distinct:
            choices.append(lat("DISTINCT", None, ws(values.value(
                inner, lambda expr: exp(RPAREN, None, after(Call(function, (expr,), True)))
            ))))

        if function.star:
            choices.append(lat("*", None, exp(RPAREN, None, after(Call(function, (STAR,))))))

        return branch(choices)

    return lat(function.name, None, exp(LPAREN, None, Thunk.deferred(options)))

def ranking(function: Function, position: Position, then: Then) -> Thunk | None:
    """`RANK() OVER (...)`, which only exists over a window."""

    if not position.reads_row:
        return None

    if function.kind is not None and not position.allows(function.kind):
        return None

    call: Call = Call(function, ())

    return lat(function.name, None, exp(EMPTY_ARGUMENTS, None, Thunk.deferred(
        lambda: over(function.ordered, lambda p, o: then(Window(call, p, o)))
    )))
