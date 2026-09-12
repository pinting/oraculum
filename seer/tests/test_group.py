"""Group indexes, and the alias resolution built on them.

A group is one inclusion minus any number of exclusions. It is fed like any
other index, and it accepts exactly when the inclusion accepts and no exclusion
does -- so while an exclusion still spells what has been matched, the group
refuses to end and generation has to continue.

`graph.alias` is the reason the type exists: an alias is the identifier pattern
minus every reserved word, table name and field name, because an alias that
spelled one of those would be ambiguous with the token it shadows.
"""

from __future__ import annotations

import pytest

import kernel as kl

from src.context import Context
from src.engine import Engine
from src.factory import IndexDraft, IndexFactory
from src.graph import IDENTIFIER, root
from src.schema import RESERVED, Schema

from .helpers import drive

def walk(
    vocabulary: kl.Vocabulary, factory: IndexFactory, draft: IndexDraft, word: str
) -> list[str]:
    """Feed `word` into one head and report the prefixes it accepted at.

    The runner notifies its resolver exactly when a head reaches an accepting
    state, so recording those notifications records where the index would let
    generation stop. The resolver answers with no children, which keeps the
    head alive for as long as the index says more may follow.
    """

    accepted: list[str] = []

    def resolve(_id: int, _payload: object, matched: str) -> list[object]:
        accepted.append(matched)

        return []

    spec = factory.spec(draft)

    assert spec is not None

    runner: kl.Runner = kl.Runner(factory.unit, 1)

    runner.set_resolver(resolve)

    assert runner.spawn(spec, None) is not None

    position: int = 0

    while position < len(word):
        allowed: dict[str, int] = {}

        for token_id in runner.routes().tolist():
            token: str | None = vocabulary.get_token_by_id(token_id)

            if token is not None and word.startswith(token, position):
                allowed[token] = token_id

        if not allowed:
            break

        longest: str = max(allowed, key=len)

        if not runner.feed(allowed[longest]):
            break

        position += len(longest)

    return accepted

IDENT: IndexDraft = IndexDraft.expression(IDENTIFIER)

class TestSubtraction:
    def test_without_exclusions_it_is_the_inclusion(
        self, vocabulary: kl.Vocabulary, factory: IndexFactory
    ) -> None:
        group: IndexDraft = IndexDraft.group(IDENT, [])

        assert walk(vocabulary, factory, group, "users") == walk(
            vocabulary, factory, IDENT, "users"
        )

    def test_an_excluded_word_never_accepts(
        self, vocabulary: kl.Vocabulary, factory: IndexFactory
    ) -> None:
        """`users` is blocked, and so is every prefix the exclusion covers."""

        group: IndexDraft = IndexDraft.group(IDENT, [IndexDraft.lattice("users")])

        assert walk(vocabulary, factory, IDENT, "users") == ["users"]
        assert walk(vocabulary, factory, group, "users") == []

    def test_growing_past_an_exclusion_frees_the_group(
        self, vocabulary: kl.Vocabulary, factory: IndexFactory
    ) -> None:
        """The exclusion dies at `users2`, so the group may end again."""

        group: IndexDraft = IndexDraft.group(IDENT, [IndexDraft.lattice("users")])

        assert walk(vocabulary, factory, group, "users2") == ["users2"]

    def test_a_prefix_of_an_exclusion_still_accepts(
        self, vocabulary: kl.Vocabulary, factory: IndexFactory
    ) -> None:
        """`use` is not `users`: only the exact word is subtracted."""

        group: IndexDraft = IndexDraft.group(IDENT, [IndexDraft.lattice("users")])

        assert walk(vocabulary, factory, group, "use") == ["use"]

    def test_many_exclusions_are_all_applied(
        self, vocabulary: kl.Vocabulary, factory: IndexFactory
    ) -> None:
        group: IndexDraft = IndexDraft.group(
            IDENT,
            [IndexDraft.lattice(word) for word in ("users", "posts", "SELECT")],
        )

        assert walk(vocabulary, factory, group, "users") == []
        assert walk(vocabulary, factory, group, "posts") == []
        assert walk(vocabulary, factory, group, "SELECT") == []
        assert walk(vocabulary, factory, group, "u") == ["u"]

    def test_groups_nest(self, vocabulary: kl.Vocabulary, factory: IndexFactory) -> None:
        """A group may stand in for either side of another group."""

        inner: IndexDraft = IndexDraft.group(IDENT, [IndexDraft.lattice("users")])
        outer: IndexDraft = IndexDraft.group(inner, [IndexDraft.lattice("posts")])

        assert walk(vocabulary, factory, outer, "users") == []
        assert walk(vocabulary, factory, outer, "posts") == []
        assert walk(vocabulary, factory, outer, "comments") == ["comments"]

class TestAliasResolution:
    def test_reserved_names_cover_keywords_and_the_schema(self, schema: Schema) -> None:
        names: tuple[str, ...] = Context(schema).get_reserved_names()

        assert "SELECT" in names
        assert "select" in names
        assert "users" in names
        assert "email" in names
        assert names == tuple(sorted(names))

        assert set(RESERVED) <= set(names)
        assert schema.get_names() <= set(names)

    def test_reserved_names_are_shared_by_copies(self, schema: Schema) -> None:
        context: Context = Context(schema)
        names: tuple[str, ...] = context.get_reserved_names()

        assert context.copy().get_reserved_names() is names

    @pytest.mark.parametrize("alias", ["u", "c", "x1", "users2", "_t"])
    def test_a_plain_alias_is_accepted(
        self, vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory, alias: str
    ) -> None:
        statement: str = f"SELECT {alias}.email FROM users AS {alias};"
        completed, matched = drive(vocabulary, schema, statement, factory=factory)

        assert completed, f"stopped at {matched!r}"
        assert matched == statement

    @pytest.mark.parametrize("alias", ["users", "posts", "email", "SELECT", "FROM"])
    def test_a_shadowing_alias_is_rejected(
        self, vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory, alias: str
    ) -> None:
        """A table, field or keyword cannot open a namespace."""

        completed, _ = drive(
            vocabulary,
            schema,
            f"SELECT {alias}.email FROM users AS {alias};",
            factory=factory,
        )

        assert not completed

    def test_the_alias_head_is_named_after_its_pattern(
        self, vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory
    ) -> None:
        """A group reports the inclusion it matches, not its own identity."""

        engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

        for token in ("SELECT", " "):
            token_id: int | None = engine.get_token_id(token)

            assert token_id is not None
            assert engine.feed(token_id)

        # The field list is open, so both a bare field and an `alias.field`
        # reference are on offer; the alias is the group.
        assert IDENTIFIER in {head.rule for head in engine.heads}
