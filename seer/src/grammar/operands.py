"""Values of the closed relation: what WHERE, GROUP BY, HAVING and ORDER BY write.

    <operand>   := <leaf> | FN "(" <operand> ")"
    <aggregate> := AGG "(" [DISTINCT] <operand> ")" | COUNT "(" "*" ")"

Once the FROM clause is closed every column is an `Operand` with a type, so a
value written after it is typed as it is written - nothing is demanded and
nothing narrowed, unlike the projection's. A function over operands is an
operand itself (`Operand.call`), which is all a condition, a grouping key or
a sort key needs to be.

Which leaves are on offer is the caller's: every column for a WHERE, the
grouped values for a HAVING, the outputs and whatever the result allows for an
ORDER BY. The leaves a function may be applied to are the caller's too, since
they are not always the same - GROUP BY offers each column once as a whole,
but `LOWER(email)` over an `email` already grouped is a key of its own.

Only scalar functions of one argument are applied here, and only where some
value it accepts can be written inside it: `F(` is offered once the classes
the arguments can produce, `depth` levels down, meet what `F` takes, so the
bracket never opens onto nothing.

Every emitter hands what it wrote to `then`, which answers with the selector
the last token takes and what follows - the selector is how a grouping key or a
sort key is committed on the token that completes it.
"""

from __future__ import annotations

from typing import Callable, Sequence

from ..context import Context
from ..model import AGGREGATES, SCALARS, Function, Kinds, TypeClass
from ..query import Operand
from ..runtime import Selector, Thunk
from .combinators import branch, dynamic, exp, guard, lat, ws
from .values import meet
from .tokens import LPAREN, RPAREN

Leaves = Callable[[Context], Sequence[Operand]]
Then = Callable[[Operand], tuple[Selector, Thunk]]

# The functions applied to operands: one argument, spelled `FN(x)`.
UNARY: tuple[Function, ...] = tuple(
    function for function in SCALARS if len(function.parameters) == 1 and function.target is None
)

def result_kind(function: Function, argument: TypeClass) -> TypeClass:
    return argument if function.kind is None else function.kind

def producible(arguments: Sequence[Operand], depth: int) -> frozenset[TypeClass]:
    """Every class a value built from `arguments` can have, nesting `depth` calls deep."""

    kinds: set[TypeClass] = {argument.kind for argument in arguments}

    for _ in range(depth):
        kinds |= {
            result_kind(function, kind)
            for function in UNARY
            for kind in kinds
            if function.accepts(0) is None or kind in function.accepts(0)  # type: ignore[operator]
        }

    return frozenset(kinds)

def _admitted(kinds: Kinds | None, produced: frozenset[TypeClass]) -> bool:
    return bool(produced if kinds is None else produced & kinds)

def operands(leaves: Leaves, arguments: Leaves, kinds: Kinds | None, then: Then, depth: int) -> Thunk:
    """A leaf of `kinds`, or a function of `kinds` over `arguments`, nested up to `depth`."""

    def build(ctx: Context) -> list[Thunk]:
        options: list[Thunk] = []

        for leaf in leaves(ctx):
            if kinds is None or leaf.kind in kinds:
                selector, following = then(leaf)

                options.append(lat(leaf.text, selector, following))

        if depth <= 0:
            return options

        produced: frozenset[TypeClass] = producible(arguments(ctx), depth - 1)

        for function in UNARY:
            if function.kind is not None:
                if kinds is not None and function.kind not in kinds:
                    continue

                accepted: Kinds | None = function.accepts(0)
            else:
                accepted = meet(function.accepts(0), kinds)

            if not _admitted(accepted, produced):
                continue

            options.append(call(function, arguments, accepted, then, depth - 1))

        return options

    return dynamic(build)

def call(function: Function, arguments: Leaves, accepted: Kinds | None, then: Then, depth: int) -> Thunk:
    """`FN(<operand>)`, committed on its closing bracket."""

    def inner(argument: Operand) -> tuple[Selector, Thunk]:
        return None, exp(RPAREN, *then(Operand.call(function, (argument,))))

    return lat(function.name, None, exp(LPAREN, None, Thunk.deferred(
        lambda: operands(arguments, arguments, accepted, inner, depth)
    )))

def aggregates(arguments: Leaves, kinds: Kinds | None, then: Then, depth: int) -> Thunk:
    """Every aggregate of `kinds` over `arguments`: `FN([DISTINCT] <operand>)`, `COUNT(*)`."""

    def of(function: Function) -> Thunk | None:
        if function.kind is not None:
            if kinds is not None and function.kind not in kinds:
                return None

            accepted: Kinds | None = function.accepts(0)
        else:
            accepted = meet(function.accepts(0), kinds)

            if accepted is not None and not accepted:
                return None

        def closed(distinct: bool) -> Callable[[Operand], tuple[Selector, Thunk]]:
            return lambda argument: (None, exp(RPAREN, *then(Operand.call(function, (argument,), distinct))))

        def fits(ctx: Context) -> bool:
            return _admitted(accepted, producible(arguments(ctx), depth - 1))

        options: list[Thunk] = [
            guard(fits, operands(arguments, arguments, accepted, closed(False), depth - 1)),
        ]

        if function.distinct:
            options.append(guard(fits, lat("DISTINCT", None, ws(
                operands(arguments, arguments, accepted, closed(True), depth - 1)
            ))))

        if function.star:
            options.append(lat("*", None, exp(RPAREN, *then(Operand.star(function)))))

        # The bracket is only offered where something fits inside it.
        opening: Thunk = lat(function.name, None, exp(LPAREN, None, branch(options)))

        return opening if function.star else guard(fits, opening)

    return branch([option for option in map(of, AGGREGATES) if option is not None])
