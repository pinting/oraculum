"""The projection: `[DISTINCT] <item> [, <item>]*`.

    <item> := <value> [AS <name>]

A value is whatever `expressions.py` writes, and its columns are demanded as
they are taken. The item itself is committed on the separator after it - the
comma, or the whitespace before `AS` or `FROM` - rather than on its own last
token, because a value does not know it is finished when its last token is
written: `id` may still become `id + 1`. The separator is the first token that
says it is, and both readings stay alive as two heads until then.

What may follow an item is read off the selection before the item is
committed: a shaped projection offers the comma only while it is short of its
arity and `FROM` only once it has it, and a named one offers `FROM` and the
comma only after an `AS` where the item has no name of its own, or one another
item already goes by.
"""

from __future__ import annotations

from typing import Callable

from ..context import Context
from ..query import Exclusion, Expr, Item, NameUse, Selection
from ..runtime import Selector, Thunk
from .combinators import branch, comma, dynamic, exp, guard, lat, name, ws
from .values import Need, Position, value
from .selectors import select, step
from .tokens import COMMA, EXPRESSION_DEPTH, WHITESPACE

_name_item: Selector = select(lambda ctx, matched: ctx.query.name_item(matched))
_use_distinct: Selector = step(lambda ctx: ctx.query.use_distinct())

def reserved(use: NameUse) -> Callable[[Context], Exclusion]:
    return lambda ctx: ctx.query.selection.reserved(use)

def item_position(selection: Selection) -> Position:
    """Where the next item is written: of the class a shape may fix.

    The item of a scalar subquery has to aggregate, which is what keeps it to
    the one row a value is.
    """

    allowed: bool = selection.allows_aggregates
    need: Need = Need.AGGREGATE if selection.contract.single_row else Need.ROW

    return Position(selection.item_kinds(), EXPRESSION_DEPTH, allowed, allowed and need is Need.ROW, need)

def items(next: Thunk) -> Thunk:
    """A comma separated item list, then `next` - which starts at `FROM`."""

    # One value grammar per position an item can be written at, built on first
    # use: building one is cheap, but every expansion would build it again.
    values: dict[Position, Thunk] = {}

    def item(ctx: Context) -> list[Thunk]:
        position: Position = item_position(ctx.query.selection)

        if position not in values:
            values[position] = value(position, end)

        return [values[position]]

    loop: Thunk = dynamic(item)

    def end(expr: Expr) -> Thunk:
        commit: Selector = select(lambda ctx, _matched: ctx.query.add_item(expr))

        def build(ctx: Context) -> list[Thunk]:
            selection: Selection = ctx.query.selection

            if not selection.admits(expr):
                return []

            unnamed: bool = not selection.needs_name(expr)
            more: bool = selection.can_follow()

            # Whether the projection may end after this item depends on what
            # it goes by - an `AS` gives it a name no requirement asks for.
            last: bool = selection.can_end(Item(expr).output)
            last_named: bool = selection.can_end(None)

            following: list[Thunk] = []

            if more:
                following.append(comma(loop))

            if last_named:
                following.append(ws(next))

            named: Thunk = branch(following)

            options: list[Thunk] = []
            after: list[Thunk] = [lat("AS", None, ws(name(reserved(NameUse.OUTPUT), _name_item, named)))]

            if unnamed and more:
                options.append(exp(COMMA, commit, loop))

            if unnamed and last:
                after.append(next)

            options.append(exp(WHITESPACE, commit, branch(after)))

            return options

        return dynamic(build)

    return loop

def projection(next: Thunk) -> Thunk:
    """The items, `DISTINCT` first where the query may deduplicate."""

    listed: Thunk = items(next)

    return branch([
        listed,
        guard(
            lambda ctx: not ctx.query.selection.is_simple,
            lat("DISTINCT", _use_distinct, ws(listed)),
        ),
    ])
