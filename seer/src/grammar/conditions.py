"""Conditions: what WHERE writes, and whatever else compares typed operands.

    <filters>   := <predicate> [(AND | OR) <predicate>]*
    <predicate> := [NOT] (<condition> | "(" <filters> ")")
    <condition> := <operand> <operator> <operand | literal | subquery>
                 | <operand> [NOT] BETWEEN <operand | literal> AND <operand | literal>
                 | <operand> [NOT] IN "(" <literal> [, <literal>]* | <subquery> ")"
                 | <operand> IS [NOT] NULL
                 | EXISTS "(" <subquery> ")"

The shape is the same wherever conditions are written; what differs is which
operands a clause may name, and that is a `Domain`. The domain emits the left
operand - it may take several tokens, `LOWER(email)` - and hands each one it
produced to the continuation, which is where the operator choices open. The
type never enters the context: an operand knows its own `Field`, so the
restriction rides in the continuation the way a join clause carries its
`Neighbor`.

A condition is recorded once written whole, on its last token. Where it took
more than one value - the bounds of a `BETWEEN`, the list of an `IN` - the
values before the last are set aside in the context's capture until then.

A subquery stands where a value of the left side's class may: as the one value
a comparison takes (`Scalar`), as the list of an `IN` (`Membership`), and on its
own after `EXISTS`. It is recorded when it closes, and it may read the columns
of the clause it stands in (`VirtualTable.exposes`), which is what makes a
subquery correlated.

Nothing is offered that leads nowhere. An operator is only offered where
something can stand opposite it, and an operand only where it takes some
operator: a class with no literal - a binary column, one of a type nobody
recognised - is compared with another column of its class or not at all, and
no subquery folds a query into one value of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from ..context import Commit, Context
from ..model import (
    AGGREGATED,
    EQUALITY,
    ORDERING,
    Arity,
    Operator,
    TypeClass,
    classify,
    is_nullable,
    literal_for,
    operators_for,
)
from ..query import Existence, Membership, Operand, Scalar
from ..runtime import Selector, Thunk
from .combinators import branch, comma, dynamic, exp, guard, keyword, lat, ws
from .selectors import select
from .subquery import bracketed, subquery
from .tokens import LPAREN, RPAREN, SPACED_LPAREN

Continuation = Callable[[Operand], Thunk]
Leaves = Callable[[Context], Sequence[Operand]]
Right = Callable[[Context, TypeClass], Sequence[Operand]]

@dataclass(frozen=True)
class Domain:
    """What one condition clause may compare."""

    left: Callable[[Continuation], Thunk]
    """Emit every left operand, continuing each with the thunk it is handed."""

    right: Right
    """The columns that may stand opposite a left operand of a class."""

    record: Callable[[Context, str], bool]
    """Commit a condition once it has been written whole."""

def opposable(right: Right, ctx: Context, left: Operand) -> bool:
    """Whether anything can stand opposite `left`: a literal of its class, or another value of it."""

    if literal_for(left.kind) is not None:
        return True

    return any(not left.same_value(other) for other in right(ctx, left.kind))

def comparable(right: Right, leaves: Leaves) -> Leaves:
    """`leaves`, without the ones no condition can be written about."""

    return lambda ctx: tuple(
        leaf for leaf in leaves(ctx) if is_nullable(leaf.field) or opposable(right, ctx, leaf)
    )

Text = Callable[[Context, str], str]

def _record(domain: Domain, text: Text) -> Selector:
    return select(lambda ctx, matched: domain.record(ctx, text(ctx, matched)))

_capture: Selector = select(lambda ctx, matched: ctx.capture(matched))
_append: Selector = select(lambda ctx, matched: ctx.append(matched))

def opposite(domain: Domain, left: Operand, selector: Selector, next: Thunk) -> Thunk:
    """What may stand opposite `left`: a column of its class, or a literal.

    This is the whole of the restriction. `left` was fixed by the caller, so
    its class is a constant here and the alternatives are simply the operands
    that share it - plus the pattern that spells a literal of that class, where
    the class has one. A class with no pattern, and `UNKNOWN` above all, is
    comparable to columns only.

    The matched text *is* the value, whether that was a column spelling or a
    literal, so one selector covers both.
    """

    kind: TypeClass = classify(left.field.type)
    pattern: str | None = literal_for(kind)

    def build(ctx: Context) -> list[Thunk]:
        options: list[Thunk] = [
            lat(right.text, selector, next)
            for right in domain.right(ctx, kind)
            # Comparing a value with itself says nothing, however it is spelled.
            if not left.same_value(right)
        ]

        if pattern is not None:
            options.append(exp(pattern, selector, next))

        return options

    return dynamic(build)

def _recorded(domain: Domain, text: str) -> Commit:
    """Record `text` once the subquery it ends with has closed."""

    return lambda ctx, _inner: domain.record(ctx, text)

def listed(domain: Domain, left: Operand, operator: Operator, next: Thunk) -> Thunk:
    """`( <literal> [, <literal>]* )` recorded on the closing bracket, or `( <subquery> )`."""

    kind: TypeClass = classify(left.field.type)
    pattern: str | None = literal_for(kind)

    assert pattern is not None, f"{operator} offered over a class with no literals"

    closing: Thunk = exp(RPAREN, _record(domain, lambda ctx, _m: f"{left.text} {operator} ({ctx.captured})"), next)

    def more() -> Thunk:
        return branch([closing, comma(exp(pattern, _append, Thunk.deferred(more)))])

    inner: Thunk = subquery(
        Membership(frozenset({kind})), next, _recorded(domain, f"{left.text} {operator} (SELECT …)")
    )

    return exp(LPAREN, None, branch([exp(pattern, _capture, Thunk.deferred(more)), inner]))

def scalar(domain: Domain, left: Operand, operator: Operator, next: Thunk) -> Thunk:
    """`( <subquery> )`, one value of `left`'s class, as the right side of a comparison."""

    purpose: Scalar = Scalar(frozenset({classify(left.field.type)}))

    return bracketed(purpose, next, _recorded(domain, f"{left.text} {operator} (SELECT …)"))

def operator_choices(domain: Domain, left: Operand, next: Thunk) -> Thunk:
    """The operators `left`'s type admits, each carrying what stands on its right.

    A unary operator ends the condition, so it takes the selector itself; the
    others defer it to the last value they are followed by.
    """

    def right(operator: Operator) -> Thunk:
        """What stands on the right of `operator`, built only once it is written."""

        arity: Arity = operator.arity

        if arity is Arity.BINARY:
            commit: Selector = _record(domain, lambda _ctx, matched: f"{left.text} {operator} {matched}")
            sides: list[Thunk] = [opposite(domain, left, commit, next)]

            # An equality or an order may compare with the one value a
            # subquery produces, where one can be of its class; a pattern
            # only with a pattern.
            if operator in EQUALITY + ORDERING and left.kind in AGGREGATED:
                sides.append(scalar(domain, left, operator, next))

            return branch(sides)

        if arity is Arity.RANGE:
            commit = _record(
                domain,
                lambda ctx, matched: f"{left.text} {operator} {ctx.captured} AND {matched}",
            )
            upper: Thunk = keyword("AND", None, ws(opposite(domain, left, commit, next)))

            return opposite(domain, left, _capture, upper)

        return listed(domain, left, operator, next)

    unary: list[Thunk] = []
    binary: list[Thunk] = []

    for operator in operators_for(left.field):
        if operator.is_unary:
            commit: Selector = _record(domain, lambda _ctx, _m, o=operator: f"{left.text} {o}")

            unary.append(lat(str(operator), commit, next))
        else:
            binary.append(lat(str(operator), None, ws(Thunk.deferred(lambda o=operator: right(o)))))

    return branch(unary + [guard(lambda ctx: opposable(domain.right, ctx, left), branch(binary))])

def condition(domain: Domain, next: Thunk) -> Thunk:
    """One comparison.

    The operand is emitted once and its operators open only behind it, so a
    step here costs a head per operand rather than a head per operand and
    operator pair.
    """

    return domain.left(lambda left: ws(operator_choices(domain, left, next)))

def predicate(domain: Domain, next: Thunk, depth: int) -> Thunk:
    """One condition, optionally parenthesised, optionally negated."""

    exists: Thunk = guard(lambda ctx: ctx.can_open_subquery(), lat("EXISTS", None, bracketed(
        Existence(), next, _recorded(domain, "EXISTS (SELECT …)"), SPACED_LPAREN
    )))

    options: list[Thunk] = [condition(domain, next), exists]

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
