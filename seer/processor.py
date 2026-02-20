import numpy as np
from numpy.typing import NDArray

import seer

class LogitsProcessor:
    def __init__(self, vocab_size: int) -> None:
        self._mask: NDArray[np.floating] = np.full(vocab_size, -np.inf, dtype=np.float32)

    def __call__(
        self,
        input_ids: NDArray[np.integer],
        scores: NDArray[np.floating],
    ) -> NDArray[np.floating]:
        routes: NDArray[np.unsignedinteger] = seer.routes()

        self._mask.fill(-np.inf)
        self._mask[routes] = 0.0

        return scores + self._mask

    def feed_token(self, token_id: int) -> int:
        return seer.feed(token_id)
