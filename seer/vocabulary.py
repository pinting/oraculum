import base64

from llama_cpp import Llama

def serialize_vocabulary(model: Llama) -> str:
    size: int = model.n_vocab()
    lines: list[str] = []

    for token_id in range(size):
        value: bytes = model.detokenize([token_id])

        if not value:
            continue

        encoded_value: str = base64.b64encode(value).decode("ascii")

        lines.append(f"{encoded_value} {token_id}")

    return "\n".join(lines) + "\n"
