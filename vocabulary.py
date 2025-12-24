import base64
from typing import List
from llama_cpp import Llama

def serialize_vocabulary(model: Llama) -> str:
    size = model.n_vocab()
    lines: List[str] = []

    for id in range(size):
        value = model.detokenize([id])

        if not value:
            continue

        encoded_value = base64.b64encode(value).decode('ascii')

        lines.append(f"{encoded_value} {id}")

    return '\n'.join(lines) + '\n'
