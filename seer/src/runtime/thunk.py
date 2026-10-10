"""The values the syntax graph is made of.

A `Thunk` is a lazily evaluated piece of the graph: given a `Context` it
produces the `Node`s that may follow. A `Node` pairs an `IndexDraft` with the
context, the selector that records what was matched, and the thunk for whatever
comes next.

A selector is the only thing that changes a context, and it never does so in
place: it answers with a modified copy, or with `None` when the selection is
one the context refuses - which ends that branch of the graph there.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Callable

from .factory import IndexDraft

if TYPE_CHECKING:
    from ..context import Context

Selector = Callable[["Context", str], "Context | None"] | None
ThunkFn = Callable[["Context"], list["Node"]]

class Thunk:
    """A node generator: terminal, ready, or deferred until first use.

    `deferred` exists so the graph can be recursive - `joins()` and
    `fields()` refer to themselves - without building it eagerly. The
    resolved function is memoised.
    """

    __slots__ = ("_fn", "_factory", "_lock", "_terminal")

    def __init__(self, fn: ThunkFn | None, factory: Callable[[], "Thunk"] | None, terminal: bool) -> None:
        self._fn = fn
        self._factory = factory
        self._lock = threading.Lock() if factory is not None else None
        self._terminal = terminal

    @classmethod
    def terminal(cls) -> "Thunk":
        return cls(None, None, True)

    @classmethod
    def new(cls, fn: ThunkFn) -> "Thunk":
        return cls(fn, None, False)

    @classmethod
    def deferred(cls, factory: Callable[[], "Thunk"]) -> "Thunk":
        return cls(None, factory, False)

    def is_terminal(self) -> bool:
        return self._terminal

    def call(self, ctx: "Context") -> list["Node"] | None:
        """Nodes that may follow, or `None` once the graph is complete."""

        if self._terminal:
            return None

        fn: ThunkFn | None = self._fn

        if fn is None:
            fn = self._resolve()

        return fn(ctx)

    def _resolve(self) -> ThunkFn:
        assert self._lock is not None and self._factory is not None

        with self._lock:
            if self._fn is None:
                resolved: Thunk = self._factory()

                if resolved._terminal:
                    self._fn = lambda _ctx: []
                elif resolved._fn is not None:
                    self._fn = resolved._fn
                else:
                    self._fn = resolved._resolve()

            return self._fn

class Node:
    """A graph node waiting for its index to be built.

    This is what a head carries as its payload, and what comes back when the
    kernel reports that head as finished.
    """

    __slots__ = ("draft", "ctx", "selector", "thunk")

    def __init__(self, draft: IndexDraft, ctx: "Context", selector: Selector, thunk: Thunk) -> None:
        self.draft = draft
        self.ctx = ctx
        self.selector = selector
        self.thunk = thunk

    def __repr__(self) -> str:
        return f"Node({self.draft})"
