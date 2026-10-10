"""The procedural generation engine.

The graph itself is made of the `Thunk`s and `Node`s of `thunk.py`; the
walking happens in the kernel. `Engine` builds the root nodes over the context
it is handed, gives them to a `kernel.Runner` as heads, and registers itself as
the runner's resolver. From then on the division of labour is:

* the **kernel** owns the indexes and the heads, advances every head over each
  token across its worker pool, and builds the indexes the next heads need;
* **seer** owns the modelling. When a head reaches the end of its index the
  kernel calls `Engine.resolve` with the head's payload - the `Node` it was
  spawned from - and whatever it matched. That is enough to find the right
  `Context`, apply the selector to it, run the thunk, and answer with the
  drafts of the indexes that may follow.

Nothing about the syntax graph is known to the kernel, and nothing about DFAs
or worker threads is known here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

import numpy as np
from numpy.typing import NDArray

import kernel as kl

from .factory import IndexFactory, IndexSpec
from .thunk import Node, Thunk

if TYPE_CHECKING:
    from ..context import Context

# One head as the kernel reports it: `id`, `index_id`, `node`, `rule`,
# `matched` and `payload`. Snapshots, not handles - the live state stays in
# the kernel.
Head = kl.Head

class Engine:
    """Drives generation: exposes the legal next tokens and consumes one."""

    __slots__ = ("_vocabulary", "_factory", "_runner")

    def __init__(
        self,
        vocabulary: kl.Vocabulary,
        context: "Context",
        thunk: Thunk,
        factory: IndexFactory | None = None,
        threads: int = 1,
    ) -> None:
        self._vocabulary = vocabulary
        self._factory = factory if factory is not None else IndexFactory(vocabulary)

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
        graph never see each other's selections, and a selector that refuses
        what was matched ends the branch with nothing to follow.

        `None` means the end of the graph; a list - possibly empty - names the
        indexes that may come next.
        """

        ctx: "Context | None" = node.ctx

        if node.selector is not None:
            ctx = node.selector(node.ctx, matched)

            if ctx is None:
                return []

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
