"""Shared fixtures.

Loading the vocabulary and building the Aho-Corasick and TokTrie bases costs
roughly half a second, so both are built once per session and reused.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import kernel as kl

from src.factory import IndexFactory
from src.schema import Schema, parse_schema

VOCABULARY_PATH: Path = Path(__file__).parent.parent.parent / "vocabulary.tiktoken"
EOS_ID: int = 1

# The schema of `experiments/9-advanced-modelling`: `id` is ambiguous across
# all three tables, `title` and `body` across two, and the foreign keys form a
# users <- posts <- comments chain with comments also pointing at users.
SCHEMA: str = """
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE posts (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL
);

CREATE TABLE comments (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    post_id BIGINT NOT NULL REFERENCES posts(id),
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL
);
"""

@pytest.fixture(scope="session")
def schema() -> Schema:
    parsed: Schema | None = parse_schema(SCHEMA)

    assert parsed is not None

    return parsed

@pytest.fixture(scope="session")
def tables(schema: Schema) -> dict[str, list[str]]:
    """The flat `table -> columns` view the resolvers take."""

    return schema.get_fields()

@pytest.fixture(scope="session")
def vocabulary() -> kl.Vocabulary:
    if not VOCABULARY_PATH.exists():
        pytest.skip(f"{VOCABULARY_PATH} is missing")

    return kl.Vocabulary.from_file_path(str(VOCABULARY_PATH), EOS_ID)

@pytest.fixture(scope="session")
def factory(vocabulary: kl.Vocabulary) -> IndexFactory:
    return IndexFactory(vocabulary)
