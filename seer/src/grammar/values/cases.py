"""CASE: `CASE WHEN <predicate> THEN <value> ... [ELSE <value>] END`.

Every branch's value has to be of one class, so a CASE is offered once per
class with a literal, the class fixed from its first token on. A predicate
compares two values of one class, the left one narrowed to it at the
operator, or tests the left one for NULL.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

from ...context import Context
from ...model import LITERAL_CLASSES, NULLITY, Arity, Kinds, TypeClass, comparisons
from ...query import Case, Column, Expr, Predicate, narrowing
from ...runtime import Thunk
from ..combinators import branch, dynamic, keyword, lat, ws
from . import values
from .narrow import can_narrow, narrower
from .position import Position, Then

def predicate(position: Position, then: Callable[[Predicate], Thunk]) -> Thunk:
    """`<value> IS [NOT] NULL`, or `<value> <operator> <value>` within one class."""

    def comparison(left: Expr) -> Thunk:
        def build(ctx: Context) -> list[Thunk]:
            options: list[Thunk] = [
                lat(str(operator), None, then(Predicate(left, operator))) for operator in NULLITY
            ]

            for kind in LITERAL_CLASSES:
                kinds: Kinds = frozenset({kind})
                columns: tuple[Column, ...] | None = narrowing(left, kinds)

                if not can_narrow(ctx, columns, kinds):
                    continue

                assert columns is not None

                right: Position = replace(position, kinds=kinds)

                for operator in comparisons(kind):
                    if operator.arity is not Arity.BINARY:
                        continue

                    options.append(lat(str(operator), narrower(columns, kinds), ws(values.value(
                        right, lambda expr, o=operator: then(Predicate(left, o, expr))
                    ))))

            return options

        return ws(dynamic(build))

    return values.value(position, comparison)

def case(position: Position, then: Then) -> Thunk:
    """`CASE WHEN ... THEN ... [ELSE ...] END`, once per class its values may have."""

    def of(kind: TypeClass) -> Thunk:
        result: Position = position.within(frozenset({kind}))
        condition: Position = position.within(None)

        def when(branches: tuple[tuple[Predicate, Expr], ...]) -> Thunk:
            def answered(test: Predicate) -> Thunk:
                return keyword("THEN", None, ws(values.value(result, lambda expr: rest(branches + ((test, expr),)))))

            return keyword("WHEN", None, ws(predicate(condition, answered)))

        def rest(branches: tuple[tuple[Predicate, Expr], ...]) -> Thunk:
            return branch([
                Thunk.deferred(lambda: when(branches)),
                keyword("ELSE", None, ws(values.value(
                    result, lambda expr: keyword("END", None, then(Case(kind, branches, expr)))
                ))),
                keyword("END", None, then(Case(kind, branches))),
            ])

        return lat("CASE", None, Thunk.deferred(lambda: when(())))

    return branch([of(kind) for kind in position.classes()])
