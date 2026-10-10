"""Conditions: what WHERE writes, and whatever else compares typed operands.

    <filters>   := <predicate> [(AND | OR) <predicate>]*
    <predicate> := [NOT] (<condition> | "(" <filters> ")")
    <condition> := <operand> <operator> <operand | literal>
                 | <operand> IS [NOT] NULL

The shape is the same wherever conditions are written; what differs is which
operands a clause may name, and that is a `Domain`. The domain emits the left
operand - it may take several tokens - and hands each one it produced to the
continuation, which is where the operator choices open. The type never enters
the context: an operand knows its own `Field`, so the restriction rides in the
continuation the way a join clause carries its `Neighbor`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from ..context import Context
from ..model import Operator, TypeClass, classify, literal_for, operators_for
from ..query.relation import Operand
from ..runtime import Selector, Thunk
from .combinators import branch, dynamic, exp, lat, ws
from .selectors import select
from .tokens import LPAREN, RPAREN

Continuation = Callable[[Operand], Thunk]

@dataclass(frozen=True)
class Domain:
    """What one condition clause may compare."""

    left: Callable[[Continuation], Thunk]
    """Emit every left operand, continuing each with the thunk it is handed."""

    right: Callable[[Context, TypeClass], Sequence[Operand]]
    """The columns that may stand opposite a left operand of a class."""

    record: Callable[[Context, str], bool]
    """Commit a condition once it has been written whole."""

def _select_condition(domain: Domain, text: Callable[[str], str]) -> Selector:
    return select(lambda ctx, matched: domain.record(ctx, text(matched)))

def right_side(domain: Domain, left: Operand, operator: Operator, next: Thunk) -> Thunk:
    """What may stand opposite `left`: a column of its class, or a literal.

    This is the whole of the restriction. `left` was fixed by the caller, so
    its class is a constant here and the alternatives are simply the operands
    that share it - plus the pattern that spells a literal of that class, where
    the class has one. A class with no pattern, and `UNKNOWN` above all, is
    comparable to columns only.

    The matched text *is* the right hand side, whether that was a column
    spelling or a literal, so one selector covers both.
    """

    kind: TypeClass = classify(left.field.type)
    commit: Selector = _select_condition(domain, lambda matched: f"{left.text} {operator} {matched}")
    pattern: str | None = literal_for(kind)

    def build(ctx: Context) -> list[Thunk]:
        options: list[Thunk] = [
            lat(right.text, commit, next)
            for right in domain.right(ctx, kind)
            # Comparing a column with itself says nothing, however it is spelled.
            if not left.same_column(right)
        ]

        if pattern is not None:
            options.append(exp(pattern, commit, next))

        return options

    return dynamic(build)

def operator_choices(domain: Domain, left: Operand, next: Thunk) -> Thunk:
    """The operators `left`'s type admits, each carrying its right hand side.

    A unary operator ends the condition, so it takes the selector itself; a
    binary one defers that to whatever `right_side` offers.
    """

    options: list[Thunk] = []

    for operator in operators_for(left.field):
        if operator.is_unary:
            commit: Selector = _select_condition(domain, lambda _m, o=operator: f"{left.text} {o}")

            options.append(lat(str(operator), commit, next))
        else:
            options.append(lat(str(operator), None, ws(right_side(domain, left, operator, next))))

    return branch(options)

def condition(domain: Domain, next: Thunk) -> Thunk:
    """One comparison.

    The operand is emitted once and its operators open only behind it, so a
    step here costs a head per operand rather than a head per operand and
    operator pair.
    """

    return domain.left(lambda left: ws(operator_choices(domain, left, next)))

def predicate(domain: Domain, next: Thunk, depth: int) -> Thunk:
    """One condition, optionally parenthesised, optionally negated."""

    options: list[Thunk] = [condition(domain, next)]

    if depth > 0:
        closing: Thunk = exp(RPAREN, None, next)

        options.append(
            exp(LPAREN, None, Thunk.deferred(lambda: filters(domain, closing, depth - 1)))
        )

    inner: Thunk = branch(options)

    return branch([inner, lat("NOT", None, ws(inner))])

def connective(next: Thunk) -> Thunk:
    return branch([
        lat("AND", None, ws(next)),
        lat("OR", None, ws(next)),
    ])

def filters(domain: Domain, next: Thunk, depth: int) -> Thunk:
    """`<predicate> [(AND | OR) <predicate>]*`, flat on purpose.

    Precedence is a parser's problem. Layering disjunction over conjunction
    would produce exactly the strings this one loop produces, since nothing
    here has to recover the tree afterwards; the parentheses of `predicate` are
    what add structure a reader can see, and they are where the cost is.
    """

    fork: Thunk = branch([
        next,
        Thunk.deferred(lambda: ws(connective(filters(domain, next, depth)))),
    ])

    return predicate(domain, fork, depth)
