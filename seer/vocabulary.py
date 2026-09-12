"""Vocabulary serialisation for llama.cpp models.

Writes a loaded model's vocabulary in the tiktoken format `kernel.Vocabulary`
expects: one `<base64 token> <id>` per line. Live mode saves the file so the
interactive driver can be pointed at the same vocabulary the model samples
from.
"""

from __future__ import annotations

import base64
from typing import Any

def serialize_vocabulary(model: Any) -> str:
    size: int = model.n_vocab()
    lines: list[str] = []

    for token_id in range(size):
        value: bytes = model.detokenize([token_id])

        if not value:
            continue

        encoded_value: str = base64.b64encode(value).decode("ascii")

        lines.append(f"{encoded_value} {token_id}")

    return "\n".join(lines) + "\n"
