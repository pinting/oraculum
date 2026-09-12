"""Behaviour of `engine.py` and `factory.py`."""

from __future__ import annotations

import pytest

import kernel as kl

from src.context import Context
from src.engine import Engine, Node, Thunk
from src.factory import DraftKind, IndexDraft, IndexFactory
from src.graph import root
from src.schema import Schema, parse_schema

from .helpers import drive

def _tiny() -> Context:
    """A one table context, for the parts that only need somewhere to stand."""

    parsed: Schema | None = parse_schema("CREATE TABLE t (\n    a INT\n);")

    assert parsed is not None

    return Context(parsed)

class TestThunk:
    def test_terminal_returns_none(self) -> None:
        assert Thunk.terminal().call(_tiny()) is None
        assert Thunk.terminal().is_terminal()

    def test_new_calls_through(self) -> None:
        thunk: Thunk = Thunk.new(lambda ctx: [])

        assert thunk.call(_tiny()) == []

    def test_deferred_is_resolved_once(self) -> None:
        calls: list[int] = []

        def factory() -> Thunk:
            calls.append(1)

            return Thunk.new(lambda ctx: [])

        thunk: Thunk = Thunk.deferred(factory)
        ctx: Context = _tiny()

        thunk.call(ctx)
        thunk.call(ctx)
        thunk.call(ctx)

        assert len(calls) == 1

    def test_deferred_terminal_yields_no_nodes(self) -> None:
        thunk: Thunk = Thunk.deferred(Thunk.terminal)

        assert thunk.call(_tiny()) == []

    def test_deferred_chain_is_flattened(self) -> None:
        inner: Thunk = Thunk.new(lambda ctx: [])
        thunk: Thunk = Thunk.deferred(lambda: Thunk.deferred(lambda: inner))

        assert thunk.call(_tiny()) == []

class TestIndexDraft:
    def test_equality_and_hashing(self) -> None:
        assert IndexDraft.lattice("a") == IndexDraft.lattice("a")
        assert IndexDraft.lattice("a") != IndexDraft.expression("a")
        assert len({IndexDraft.lattice("a"), IndexDraft.lattice("a")}) == 1
        assert IndexDraft.lattice("a") != "a"

    def test_kinds(self) -> None:
        assert IndexDraft.lattice("a").kind is DraftKind.LATTICE
        assert IndexDraft.expression("a").kind is DraftKind.EXPRESSION

    def test_group_is_keyed_by_its_members(self) -> None:
        include: IndexDraft = IndexDraft.expression("a+")
        one: IndexDraft = IndexDraft.group(include, [IndexDraft.lattice("aa")])
        same: IndexDraft = IndexDraft.group(include, [IndexDraft.lattice("aa")])
        other: IndexDraft = IndexDraft.group(include, [IndexDraft.lattice("ab")])

        assert one.kind is DraftKind.GROUP
        assert one == same
        assert one != other
        assert one != include
        assert len({one, same, other}) == 2

    def test_group_reports_its_inclusion(self) -> None:
        """A head on a group is named after the shape it matches."""

        include: IndexDraft = IndexDraft.expression("a+")
        group: IndexDraft = IndexDraft.group(include, [IndexDraft.lattice("aa")])

        assert group.include is include
        assert group.label() == "a+"

class TestIndexFactory:
    def test_builds_and_memoises(self, factory: IndexFactory) -> None:
        draft: IndexDraft = IndexDraft.lattice("SELECT")

        first: int | None = factory.create_index(draft)
        before: int = factory.builds
        second: int | None = factory.create_index(draft)

        assert first is not None
        assert first == second
        assert factory.builds == before
        assert factory.is_cached(draft)

    def test_invalid_pattern_returns_none(self, factory: IndexFactory) -> None:
        assert factory.create_index(IndexDraft.expression("[")) is None

    def test_uncached_factory_rebuilds(self, vocabulary: kl.Vocabulary) -> None:
        uncached: IndexFactory = IndexFactory(vocabulary, cache=False)
        draft: IndexDraft = IndexDraft.lattice("SELECT")

        assert uncached.create_index(draft) != uncached.create_index(draft)
        assert not uncached.is_cached(draft)

    def test_group_members_are_built_first(self, factory: IndexFactory) -> None:
        """A group spec names its members by id, so they exist before it does."""

        include: IndexDraft = IndexDraft.expression("[a-z]+")
        exclude: IndexDraft = IndexDraft.lattice("abc")
        group: IndexDraft = IndexDraft.group(include, [exclude])

        spec = factory.spec(group)

        assert spec is not None

        kind, include_id, exclude_ids = spec

        assert kind == "group"
        assert include_id == factory.create_index(include)
        assert exclude_ids == [factory.create_index(exclude)]

        index: int | None = factory.create_index(group)

        assert index is not None
        assert factory.label(index) == "[a-z]+"

    def test_unbuildable_group_member_is_reported(self, factory: IndexFactory) -> None:
        group: IndexDraft = IndexDraft.group(
            IndexDraft.expression("["), [IndexDraft.lattice("a")]
        )

        assert factory.spec(group) is None
        assert factory.create_index(group) is None

def _runner(factory: IndexFactory, resolver) -> kl.Runner:
    runner: kl.Runner = kl.Runner(factory.unit, 1)

    runner.set_resolver(resolver)

    return runner

class TestHead:
    """Heads live in the kernel; seer only sees them through the runner."""

    def test_feed_and_match(self, vocabulary: kl.Vocabulary, factory: IndexFactory) -> None:
        finished: list[tuple[Node, str]] = []
        ctx: Context = _tiny()
        node: Node = Node(IndexDraft.lattice("SELECT"), ctx, None, Thunk.terminal())

        def resolve(_id: int, payload: Node, matched: str) -> None:
            finished.append((payload, matched))

            return None

        runner: kl.Runner = _runner(factory, resolve)

        assert runner.spawn(("lattice", "SELECT"), node) is not None
        assert len(runner) == 1

        token_id: int | None = vocabulary.get_id_by_token("SELECT")

        assert token_id is not None
        assert runner.feed(token_id) is True
        assert finished == [(node, "SELECT")]
        assert runner.is_completed()

    def test_feed_rejects_unknown_token(
        self, vocabulary: kl.Vocabulary, factory: IndexFactory
    ) -> None:
        runner: kl.Runner = _runner(factory, lambda _id, _payload, _matched: None)

        runner.spawn(("lattice", "SELECT"), None)

        token_id: int | None = vocabulary.get_id_by_token("FROM")

        assert token_id is not None
        assert runner.feed(token_id) is False
        assert len(runner) == 0

    def test_unbuildable_index_spawns_nothing(self, factory: IndexFactory) -> None:
        runner: kl.Runner = _runner(factory, lambda _id, _payload, _matched: None)

        assert runner.spawn(("expression", "["), None) is None
        assert len(runner) == 0

    def test_resolver_errors_are_raised_by_feed(
        self, vocabulary: kl.Vocabulary, factory: IndexFactory
    ) -> None:
        """A callback that raises must not be swallowed inside the kernel."""

        def resolve(_id: int, _payload: object, _matched: str) -> None:
            raise KeyError("boom")

        runner: kl.Runner = _runner(factory, resolve)

        runner.spawn(("lattice", "SELECT"), None)

        token_id: int | None = vocabulary.get_id_by_token("SELECT")

        assert token_id is not None

        with pytest.raises(KeyError):
            runner.feed(token_id)

class TestEngine:
    def test_starts_at_select(self, vocabulary: kl.Vocabulary, schema, factory: IndexFactory) -> None:
        engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

        assert not engine.is_completed()
        assert engine.matched() == ""

        tokens = {engine.get_token(i) for i in engine.routes().tolist()}

        assert "SELECT" in tokens
        assert "FROM" not in tokens

    def test_rejects_terminal_root(self, vocabulary: kl.Vocabulary, schema) -> None:
        with pytest.raises(ValueError):
            Engine(vocabulary, schema, Thunk.terminal())

    def test_feed_rejects_illegal_token(self, vocabulary: kl.Vocabulary, schema, factory: IndexFactory) -> None:
        engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

        token_id: int | None = vocabulary.get_id_by_token("FROM")

        assert token_id is not None
        assert engine.feed(token_id) is False
        assert list(engine.heads) == []

    def test_token_lookup_round_trips(self, vocabulary: kl.Vocabulary, schema, factory: IndexFactory) -> None:
        engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

        token_id: int | None = engine.get_token_id("SELECT")

        assert token_id is not None
        assert engine.get_token(token_id) == "SELECT"

    def test_completed_statement_has_no_routes(
        self, vocabulary: kl.Vocabulary, schema, factory: IndexFactory
    ) -> None:
        completed, matched = drive(vocabulary, schema, "SELECT email FROM users;", factory=factory)

        assert completed
        assert matched == "SELECT email FROM users;"
