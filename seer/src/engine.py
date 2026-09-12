"""The procedural generation engine.

A `Thunk` is a lazily evaluated piece of the syntax graph: given a `Context` it
produces the `Node`s that may follow. A `Node` pairs an `IndexDraft` with the
context, the selector that records what was matched, and the thunk for whatever
comes next.

The walking itself happens in the kernel. `Engine` builds the root nodes, hands
them to a `kernel.Runner` as heads, and registers itself as the runner's
resolver. From then on the division of labour is:

* the **kernel** owns the indexes and the heads, advances every head over each
  token across its worker pool, and builds the indexes the next heads need;
* **seer** owns the modelling. When a head reaches the end of its index the
  kernel calls `Engine.resolve` with the head's payload -- the `Node` it was
  spawned from -- and whatever it matched. That is enough to find the right
  `Context`, apply the selector to it, run the thunk, and answer with the
  drafts of the indexes that may follow.

Nothing about the syntax graph is known to the kernel, and nothing about DFAs
or worker threads is known here.
"""

from __future__ import annotations

import threading
from typing import Callable, Sequence

import numpy as np
from numpy.typing import NDArray

import kernel as kl

from .context import Context
from .factory import IndexDraft, IndexFactory, IndexSpec
from .schema import Schema

Selector = Callable[[Context, str], Context] | None
ThunkFn = Callable[[Context], list["Node"]]

# One head as the kernel reports it: `id`, `index_id`, `node`, `rule`,
# `matched` and `payload`. Snapshots, not handles -- the live state stays in
# the kernel.
Head = kl.Head

class Thunk:
    """A node generator: terminal, ready, or deferred until first use.

    `deferred` exists so the graph can be recursive -- `joins()` and
    `fields()` refer to themselves -- without building it eagerly. The
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

    def call(self, ctx: Context) -> list["Node"] | None:
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

    def __init__(self, draft: IndexDraft, ctx: Context, selector: Selector, thunk: Thunk) -> None:
        self.draft = draft
        self.ctx = ctx
        self.selector = selector
        self.thunk = thunk

    def __repr__(self) -> str:
        return f"Node({self.draft})"

class Engine:
    """Drives generation: exposes the legal next tokens and consumes one."""

    __slots__ = ("_vocabulary", "_factory", "_runner")

    def __init__(
        self,
        vocabulary: kl.Vocabulary,
        schema: Schema,
        thunk: Thunk,
        factory: IndexFactory | None = None,
        threads: int = 1,
    ) -> None:
        self._vocabulary = vocabulary
        self._factory = factory if factory is not None else IndexFactory(vocabulary)

        context: Context = Context(schema)
        nodes: list[Node] | None = thunk.call(context)

        if nodes is None:
            raise ValueError("Root thunk is terminal")

        self._runner = kl.Runner(self._factory.unit, threads)

        self._runner.set_resolver(self.resolve)
        self._runner.spawn_many(self._requests(nodes))

        # A root index that accepts the empty word is finished the moment it
        # exists, so give the resolve loop a turn before the first token.
        self._runner.settle()

    @property
    def factory(self) -> IndexFactory:
        return self._factory

    @property
    def runner(self) -> kl.Runner:
        return self._runner

    @property
    def threads(self) -> int:
        return self._runner.workers

    @property
    def heads(self) -> Sequence[Head]:
        """A snapshot of the active indexes."""

        return self._runner.heads()

    def resolve(self, _head_id: int, node: Node, matched: str) -> list[tuple[IndexSpec, Node]] | None:
        """Turn a finished head into the heads that follow it.

        Called by the kernel, with the GIL taken back for the duration. The
        selector runs on a copy of the node's context, so the branches of the
        graph never see each other's selections.

        `None` means the end of the graph; a list -- possibly empty -- names the
        indexes that may come next.
        """

        ctx: Context = node.ctx

        if node.selector is not None:
            ctx = node.selector(ctx, matched)

        children: list[Node] | None = node.thunk.call(ctx)

        if children is None:
            return None

        return self._requests(children)

    def _requests(self, nodes: Sequence[Node]) -> list[tuple[IndexSpec, Node]]:
        """Pair each node with the kernel spec of the index it wants.

        A node whose index cannot be built is dropped rather than raised on,
        because expansion is speculative: an unbuildable alternative is simply
        one the language does not offer.
        """

        requests: list[tuple[IndexSpec, Node]] = []

        for node in nodes:
            spec: IndexSpec | None = self._factory.spec(node.draft)

            if spec is not None:
                requests.append((spec, node))

        return requests

    def routes(self) -> NDArray[np.uint64]:
        """Every token id that at least one live head would accept."""

        return self._runner.routes()

    def get_token(self, token_id: int) -> str | None:
        return self._vocabulary.get_token_by_id(token_id)

    def get_token_id(self, token: str) -> int | None:
        return self._vocabulary.get_id_by_token(token)

    def is_completed(self) -> bool:
        return self._runner.is_completed()

    def feed(self, token_id: int) -> bool:
        """Consume a token and re-resolve the graph.

        Returns whether any head accepted it. A rejected token leaves the
        engine with no live heads.
        """

        return self._runner.feed(token_id)

    def matched(self) -> str:
        return self._runner.matched()

    def __len__(self) -> int:
        return len(self._runner)
