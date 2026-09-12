"""The kernel's worker pool.

Feeding a token advances every head, and building the indexes the next heads
need is the expensive stage; both are spread over the pool. The contract is
that the number of workers changes nothing an observer can see: same heads,
same routes, same accepted language, same number of index builds.

`src/graph.py` is recursive and its thunks are shared between branches, so the
memoisation that keeps it cheap has to hold up while the resolver is being
called for one head after another.
"""

from __future__ import annotations

import threading

import pytest

import kernel as kl

from src.context import Context
from src.engine import Engine, Thunk
from src.factory import IndexDraft, IndexFactory
from src.graph import root
from src.schema import parse_schema

from .helpers import drive, trace

WORKERS: list[int] = [1, 2, 8]

STATEMENTS: list[str] = [
    "SELECT email FROM users;",
    "SELECT email, first_name FROM users;",
    "SELECT c.body FROM comments AS c;",
    "SELECT email, title FROM users INNER JOIN posts ON users.id = posts.user_id;",
    "SELECT title, c.body FROM posts LEFT JOIN comments AS c ON posts.id = c.post_id;",
    "SELECT email, title, c.body FROM users INNER JOIN posts ON users.id = posts.user_id"
    " INNER JOIN comments AS c ON posts.id = c.post_id;",
]

class TestEquivalence:
    @pytest.mark.parametrize("statement", STATEMENTS)
    @pytest.mark.parametrize("workers", WORKERS)
    def test_same_language(
        self,
        vocabulary: kl.Vocabulary,
        schema,
        factory: IndexFactory,
        statement: str,
        workers: int,
    ) -> None:
        serial = drive(vocabulary, schema, statement, factory.fork(), threads=1)
        parallel = drive(vocabulary, schema, statement, factory.fork(), threads=workers)

        assert serial == parallel
        assert serial == (True, statement)

    @pytest.mark.parametrize("statement", STATEMENTS)
    @pytest.mark.parametrize("workers", WORKERS)
    def test_same_heads_at_every_step(
        self,
        vocabulary: kl.Vocabulary,
        schema,
        factory: IndexFactory,
        statement: str,
        workers: int,
    ) -> None:
        serial = trace(vocabulary, schema, statement, factory.fork(), threads=1)
        parallel = trace(vocabulary, schema, statement, factory.fork(), threads=workers)

        assert serial == parallel

    @pytest.mark.parametrize("workers", WORKERS)
    def test_same_number_of_builds(
        self, vocabulary: kl.Vocabulary, schema, factory: IndexFactory, workers: int
    ) -> None:
        """A draft is built once however many workers ask for it at once."""

        statement: str = STATEMENTS[-1]

        cold: IndexFactory = factory.fork()
        warm: IndexFactory = factory.fork()

        drive(vocabulary, schema, statement, cold, threads=1)
        drive(vocabulary, schema, statement, warm, threads=workers)

        assert cold.builds == warm.builds

class TestSharing:
    def test_cached_index_is_shared(self, factory: IndexFactory) -> None:
        """Two heads over the same draft walk one index."""

        shared: IndexFactory = factory.fork()
        draft: IndexDraft = IndexDraft.expression("[a-z]+")

        first: int | None = shared.create_index(draft)
        builds: int = shared.builds

        assert first == shared.create_index(draft)
        assert shared.builds == builds

    def test_deferred_thunk_is_resolved_once(self) -> None:
        """`Thunk.deferred` memoises under contention, not merely in order."""

        calls: list[int] = []
        gate = threading.Barrier(8)

        def make() -> Thunk:
            calls.append(1)

            return Thunk.new(lambda ctx: [])

        thunk: Thunk = Thunk.deferred(make)
        parsed = parse_schema("CREATE TABLE t (\n    a INT\n);")

        assert parsed is not None

        ctx: Context = Context(parsed)

        def run() -> None:
            gate.wait()

            thunk.call(ctx)

        threads = [threading.Thread(target=run) for _ in range(8)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(calls) == 1

class TestConfiguration:
    def test_worker_count_is_reported(
        self, vocabulary: kl.Vocabulary, schema, factory: IndexFactory
    ) -> None:
        engine: Engine = Engine(
            vocabulary, schema, root(), factory=factory.fork(), threads=4
        )

        assert engine.threads == 4

    def test_zero_workers_uses_every_core(
        self, vocabulary: kl.Vocabulary, schema, factory: IndexFactory
    ) -> None:
        engine: Engine = Engine(
            vocabulary, schema, root(), factory=factory.fork(), threads=0
        )

        assert engine.threads >= 1

    def test_stats_are_recorded(
        self, vocabulary: kl.Vocabulary, schema, factory: IndexFactory
    ) -> None:
        engine: Engine = Engine(
            vocabulary, schema, root(), factory=factory.fork(), threads=4
        )

        drive_engine: str = STATEMENTS[0]
        position: int = 0

        while position < len(drive_engine):
            allowed: dict[str, int] = {}

            for token_id in engine.routes().tolist():
                token: str | None = engine.get_token(token_id)

                if token is not None and drive_engine.startswith(token, position):
                    allowed[token] = token_id

            longest: str = max(allowed, key=len)

            engine.feed(allowed[longest])

            position += len(longest)

        rounds, notified, spawned = engine.runner.stats

        assert rounds > 0
        assert notified > 0
        assert spawned > 0
