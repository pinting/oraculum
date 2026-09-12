"""llama.cpp logits processor.

Port of `seer/processor.py`. The Rust build reached into the `seer` extension
module for `routes` / `feed`; the port reaches into `core` instead, which holds
the same state.

Passing an `Engine` explicitly bypasses `core` and drives that engine directly,
which is what the tests do.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

import core
from src import Engine

class LogitsProcessor:
    __slots__ = ("_engine", "_mask")

    def __init__(self, vocab_size: int, engine: Engine | None = None) -> None:
        self._engine = engine
        self._mask: NDArray[np.float32] = np.full(vocab_size, -np.inf, dtype=np.float32)

    @property
    def engine(self) -> Engine | None:
        return self._engine

    def __call__(
        self,
        input_ids: NDArray[np.integer],
        scores: NDArray[np.floating],
    ) -> NDArray[np.floating]:
        routes: NDArray[np.uint64] = (
            core.routes() if self._engine is None else self._engine.routes()
        )

        self._mask.fill(-np.inf)

        if routes.size:
            self._mask[routes] = 0.0

        return scores + self._mask

    def feed(self, token_id: int) -> int:
        """Consume a sampled token. Returns 0 on success, as in the Rust API.

        Unlike `seer/src/lib.rs`, which discarded the engine's own result, a
        token the graph rejects is reported as 1 so the generation loop stops.
        """

        if self._engine is None:
            return core.feed(token_id)

        return 0 if self._engine.feed(token_id) else 1

    def is_completed(self) -> bool:
        engine: Engine | None = self._engine if self._engine is not None else core.get_engine()

        return engine is not None and engine.is_completed()
