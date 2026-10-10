"""Narrowing a value written where its class was free, once something asks for one.

`id + 1` only learns that `id` is numeric at the `+`, and `x = 'a'` inside a
CASE that `x` is text at the `=`. What has to be narrowed is the columns the
value follows (`expression.narrowing`); the operator is offered only where the
algebra can still hold them to the class, and its selector applies it.
"""

from __future__ import annotations

from ...context import Context
from ...model import Kinds
from ...query import Column
from ...runtime import Selector
from ..selectors import select

def narrower(columns: tuple[Column, ...], kinds: Kinds) -> Selector:
    """Narrow `columns` to `kinds`; nothing to do where a value's shape already fixes it."""

    if not columns:
        return None

    return select(lambda ctx, _matched: ctx.query.narrow(columns, kinds))

def can_narrow(ctx: Context, columns: tuple[Column, ...] | None, kinds: Kinds) -> bool:
    if columns is None:
        return False

    return not columns or ctx.query.selection.can_narrow(columns, kinds)
