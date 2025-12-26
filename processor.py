from numpy.typing import NDArray
import numpy as np

class LogitsProcessor:
    def __call__(
        self,
        input_ids: NDArray[np.intc],
        scores: NDArray[np.single]
    ) -> NDArray[np.single]:
        return scores
