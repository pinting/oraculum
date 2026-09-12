"""Shared setup for the drivers.

Holds the vocabulary and the engine as module state and exposes `routes` and
`feed` over them, so a caller that has no engine of its own - the logits
processor of `processor.py` - can still reach one.

Both modes of `main.py`, interactive and model driven, build their engine
through `init_engine`. The `int` returns are a status code rather than a raised
exception, because the initialisation steps are also called one at a time.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

import kernel as kl

from src import Engine, IndexFactory, Schema, parse_schema, root

VOCABULARY_PATH: str = "../vocabulary.tiktoken"
EOS_ID: int = 1

SCHEMA: str = """
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    verified BOOLEAN,
    created_at TIMESTAMP
);

CREATE TABLE posts (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    published_at TIMESTAMP
);

CREATE TABLE comments (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    post_id BIGINT NOT NULL REFERENCES posts(id),
    body TEXT NOT NULL
);
"""

schema: str = SCHEMA

_vocabulary: kl.Vocabulary | None = None
_engine: Engine | None = None

def set_schema(_schema: str) -> None:
    global schema

    schema = _schema

def get_schema() -> str:
    return schema

def load_vocabulary(path: str) -> bytes:
    with open(path, "r", encoding="utf-8") as handle:
        data: str = handle.read()

    return data.encode("utf-8")

def init_vocabulary(data: bytes, eos_id: int) -> int:
    """Load the vocabulary. Returns 0 on success."""

    global _vocabulary

    try:
        vocabulary: kl.Vocabulary = kl.Vocabulary(data, eos_id)
    except Exception:
        return 1

    tokens: int = len(vocabulary.get_tokens())

    # `kernel` accepts malformed input and yields an empty vocabulary rather
    # than failing, which would silently build an engine with no routes.
    if tokens == 0:
        return 1

    print(f"Loaded {tokens} tokens")

    _vocabulary = vocabulary

    return 0

def init_schema(data: bytes, threads: int = 1) -> int:
    """Parse the schema and build the engine over the loaded vocabulary."""

    global _engine

    try:
        text: str = data.decode("utf-8")
    except UnicodeDecodeError:
        return 1

    print(f"Schema:\n{text}")

    schema: Schema | None = parse_schema(text)

    if schema is None:
        return 1

    print(f"Tables: {schema.get_fields()}")

    if _vocabulary is None:
        return 1

    try:
        engine: Engine = Engine(
            _vocabulary,
            schema,
            root(),
            factory=IndexFactory(_vocabulary),
            threads=threads,
        )
    except ValueError:
        return 1

    _engine = engine

    return 0

def init_engine(vocabulary_data: bytes, eos_id: int, schema: str, threads: int = 1) -> Engine:
    """Load the vocabulary and build the engine, raising on failure."""

    if init_vocabulary(vocabulary_data, eos_id) != 0:
        raise RuntimeError("Failed to initialize vocabulary")

    if init_schema(schema.encode("utf-8"), threads) != 0:
        raise RuntimeError("Failed to initialize schema")

    assert _engine is not None

    return _engine

def get_engine() -> Engine | None:
    return _engine

def get_vocabulary() -> kl.Vocabulary | None:
    return _vocabulary

def routes() -> NDArray[np.uint64]:
    if _engine is None:
        return np.empty(0, dtype=np.uint64)

    return _engine.routes()

def feed(token_id: int) -> int:
    """Consume a token. Returns 0 on success."""

    if _engine is None:
        return 1

    _engine.feed(token_id)

    return 0

def get_token_by_id(token_id: int) -> str | None:
    if _vocabulary is None:
        return None

    return _vocabulary.get_token_by_id(token_id)

def get_id_by_token(token: str) -> int | None:
    if _vocabulary is None:
        return None

    return _vocabulary.get_id_by_token(token)

def shutdown() -> None:
    """Drop the engine, releasing the kernel's worker pool with it."""

    global _engine

    _engine = None
