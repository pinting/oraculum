"""The bridge from what was matched to what the context records.

Every selector has the same shape: copy the context, apply one operation to
the copy, and hand the copy on - or hand on nothing, when the operation
refuses, which ends the branch there instead of carrying a context forward
that never recorded what the text says it did.
"""

from __future__ import annotations

from typing import Callable

from ..context import Context
from ..runtime import Selector

Apply = Callable[[Context, str], bool]

def select(apply: Apply) -> Selector:
    """A selector applying `apply(copy, matched)` to a copy of the context."""

    def selector(ctx: Context, matched: str) -> Context | None:
        clone: Context = ctx.copy()

        return clone if apply(clone, matched) else None

    return selector

def step(apply: Callable[[Context], bool]) -> Selector:
    """A selector for a keyword, whose matched text says nothing new."""

    return select(lambda ctx, _matched: apply(ctx))
