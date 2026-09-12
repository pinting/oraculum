"""The driver seam shared by `main.py` and `live.py`.

`core.py` holds the vocabulary and the engine as module state, so these tests
cover the globals as well as the helpers around them.
"""

from __future__ import annotations

import numpy as np
import pytest

import kernel as kl

import core
from processor import LogitsProcessor
from src import Engine

from .helpers import drive

@pytest.fixture(autouse=True)
def reset_core():
    """Restore the module globals so tests do not leak into each other."""

    yield

    core.shutdown()

    core._vocabulary = None
    core._engine = None
    core.schema = core.SCHEMA

class TestSchemaState:
    def test_defaults_to_the_builtin_schema(self) -> None:
        assert "CREATE TABLE users" in core.get_schema()

    def test_set_schema_round_trips(self) -> None:
        core.set_schema("CREATE TABLE t (\n    a INT\n);")

        assert core.get_schema() == "CREATE TABLE t (\n    a INT\n);"

    def test_load_vocabulary_reads_bytes(self, tmp_path) -> None:
        path = tmp_path / "vocab.tiktoken"
        path.write_text("dGVzdA== 0\n", encoding="utf-8")

        assert core.load_vocabulary(str(path)) == b"dGVzdA== 0\n"

class TestUninitialised:
    def test_routes_is_empty(self) -> None:
        assert core.routes().size == 0

    def test_feed_reports_failure(self) -> None:
        assert core.feed(0) == 1

    def test_token_lookups_return_none(self) -> None:
        assert core.get_token_by_id(0) is None
        assert core.get_id_by_token("SELECT") is None

    def test_init_schema_without_vocabulary_fails(self) -> None:
        assert core.init_schema(core.SCHEMA.encode("utf-8")) == 1

class TestInitEngine:
    def test_builds_a_working_engine(self, vocabulary: kl.Vocabulary, tmp_path) -> None:
        raw: bytes = core.load_vocabulary(str(_vocabulary_path()))

        engine: Engine = core.init_engine(raw, core.EOS_ID, core.SCHEMA)

        assert isinstance(engine, Engine)
        assert core.get_engine() is engine
        assert core.get_vocabulary() is not None

        token_id: int | None = core.get_id_by_token("SELECT")

        assert token_id is not None
        assert core.get_token_by_id(token_id) == "SELECT"
        assert token_id in core.routes().tolist()
        assert core.feed(token_id) == 0
        assert engine.matched() == "SELECT"

    def test_threads_reach_the_kernel(self) -> None:
        raw: bytes = core.load_vocabulary(str(_vocabulary_path()))

        engine: Engine = core.init_engine(raw, core.EOS_ID, core.SCHEMA, threads=4)

        assert engine.threads == 4

        core.shutdown()

        assert core.get_engine() is None

    def test_bad_vocabulary_raises(self) -> None:
        with pytest.raises(RuntimeError, match="vocabulary"):
            core.init_engine(b"not a vocabulary", core.EOS_ID, core.SCHEMA)

    def test_bad_schema_raises(self) -> None:
        raw: bytes = core.load_vocabulary(str(_vocabulary_path()))

        with pytest.raises(RuntimeError, match="schema"):
            core.init_engine(raw, core.EOS_ID, "SELECT 1;")

class TestLogitsProcessor:
    def test_masks_everything_outside_the_routes(
        self, vocabulary: kl.Vocabulary, schema, factory
    ) -> None:
        from src import root

        engine: Engine = Engine(vocabulary, schema, root(), factory=factory.fork())
        size: int = len(vocabulary.get_ids()) + 1

        processor: LogitsProcessor = LogitsProcessor(size, engine)

        scores = np.zeros(size, dtype=np.float32)
        masked = processor(np.zeros(0, dtype=np.int32), scores)

        allowed: list[int] = engine.routes().tolist()

        assert np.isfinite(masked[allowed]).all()
        assert np.isneginf(masked).sum() == size - len(allowed)

    def test_feed_reports_rejection(self, vocabulary: kl.Vocabulary, schema, factory) -> None:
        from src import root

        engine: Engine = Engine(vocabulary, schema, root(), factory=factory.fork())
        processor: LogitsProcessor = LogitsProcessor(8, engine)

        select_id: int | None = vocabulary.get_id_by_token("SELECT")
        from_id: int | None = vocabulary.get_id_by_token("FROM")

        assert select_id is not None and from_id is not None
        assert processor.feed(select_id) == 0
        assert processor.feed(from_id) == 1

    def test_reports_completion(self, vocabulary: kl.Vocabulary, schema, factory) -> None:
        from src import root

        engine: Engine = Engine(vocabulary, schema, root(), factory=factory.fork())
        processor: LogitsProcessor = LogitsProcessor(8, engine)

        assert not processor.is_completed()

        for token in ["SELECT", " ", "email", " ", "FROM", " ", "users", ";"]:
            token_id: int | None = vocabulary.get_id_by_token(token)

            assert token_id is not None
            assert processor.feed(token_id) == 0

        assert processor.is_completed()

    def test_falls_back_to_core(self) -> None:
        raw: bytes = core.load_vocabulary(str(_vocabulary_path()))

        core.init_engine(raw, core.EOS_ID, core.SCHEMA)

        processor: LogitsProcessor = LogitsProcessor(8)

        assert processor.engine is None
        assert processor.feed(core.get_id_by_token("SELECT")) == 0
        assert not processor.is_completed()

def _vocabulary_path():
    from conftest import VOCABULARY_PATH

    return VOCABULARY_PATH
