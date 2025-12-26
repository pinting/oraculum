from numpy.typing import NDArray
import numpy as np
import oraculum

class LogitsProcessor:
    def __init__(self, vocab_size: int) -> None:
        self._mask: NDArray[np.single] = np.full(vocab_size, -np.inf, dtype=np.float32)

    def __call__(
        self,
        input_ids: NDArray[np.intc],
        scores: NDArray[np.single]
    ) -> NDArray[np.single]:
        routes: NDArray[np.uint32] = oraculum.routes()

        self._mask.fill(-np.inf)
        self._mask[routes] = 0.0

        return scores + self._mask

    def feed_token(self, token_id: int) -> int:
        return oraculum.feed(token_id)
