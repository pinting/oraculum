"""The language accepted by `src/graph.py`.

    SELECT <fields> FROM <entry> [, <entry>]* ;
    <entry> := <table> [AS <alias>] [<join type> <table> [AS <alias>] ON a = b]*

Rejection is the interesting half: it is what the modelling buys over a plain
grammar, which would accept any table after FROM and any column before it.
"""

from __future__ import annotations

import pytest

import kernel as kl

from src.engine import Engine
from src.factory import IndexFactory
from src.graph import COMMA, IDENTIFIER, WHITESPACE, root
from src.schema import Schema

from .helpers import drive

ACCEPTED: list[str] = [
    "SELECT email FROM users;",
    "SELECT email, first_name FROM users;",
    "SELECT c.body FROM comments AS c;",
    "SELECT u.email, u.first_name FROM users AS u;",
    # a join, in both directions
    "SELECT email, title FROM users INNER JOIN posts ON users.id = posts.user_id;",
    "SELECT email, title FROM posts INNER JOIN users ON posts.user_id = users.id;",
    # every join type
    "SELECT email, title FROM users LEFT JOIN posts ON users.id = posts.user_id;",
    "SELECT email, title FROM users RIGHT JOIN posts ON users.id = posts.user_id;",
    "SELECT email, title FROM users FULL JOIN posts ON users.id = posts.user_id;",
    # an aliased join target
    "SELECT title, c.body FROM posts INNER JOIN comments AS c ON posts.id = c.post_id;",
    # a chain: the second join is only reachable after the first merges posts in
    "SELECT email, title, c.body FROM users INNER JOIN posts ON users.id = posts.user_id"
    " INNER JOIN comments AS c ON posts.id = c.post_id;",
]

REJECTED: list[str] = [
    # first_name is only on users
    "SELECT first_name FROM comments;",
    # post_id needs comments, which is not in the FROM clause
    "SELECT post_id FROM users;",
    # a table no selected field requires
    "SELECT email FROM posts;",
    # the ON columns are not a foreign key pair
    "SELECT email, title FROM users INNER JOIN posts ON users.id = posts.id;",
    # no foreign key between a table and itself
    "SELECT email FROM users INNER JOIN users ON users.id = users.id;",
    # the alias is bound to a table without that field
    "SELECT c.first_name FROM comments AS c;",
    # a field in no table at all
    "SELECT nope FROM users;",
    # missing terminator
    "SELECT email FROM users",
    # an unaliased join target cannot satisfy an aliased requirement
    "SELECT c.body FROM comments;",
]

@pytest.mark.parametrize("statement", ACCEPTED)
def test_accepted(
    vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory, statement: str
) -> None:
    completed, matched = drive(vocabulary, schema, statement, factory=factory)

    assert completed, f"stopped at {matched!r}"
    assert matched == statement

@pytest.mark.parametrize("statement", REJECTED)
def test_rejected(
    vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory, statement: str
) -> None:
    completed, _ = drive(vocabulary, schema, statement, factory=factory)

    assert not completed

def _feed(engine: Engine, text: str) -> None:
    """Consume `text`, taking the longest legal token at each step.

    Pieces such as `INNER JOIN` or `users.id` span several vocabulary tokens,
    so they cannot be fed one lookup at a time.
    """

    position: int = 0

    while position < len(text):
        allowed: dict[str, int] = {}

        for token_id in engine.routes().tolist():
            token: str | None = engine.get_token(token_id)

            if token is not None and text.startswith(token, position):
                allowed[token] = token_id

        assert allowed, f"stuck at {text[position:]!r} (matched {engine.matched()!r})"

        longest: str = max(allowed, key=len)

        assert engine.feed(allowed[longest]), longest

        position += len(longest)

PATTERNS: frozenset[str] = frozenset({IDENTIFIER, WHITESPACE, COMMA})

def _rules(engine: Engine) -> set[str]:
    """The constant alternatives on offer, ignoring the separator patterns."""

    return {head.rule for head in engine.heads if head.rule not in PATTERNS}

def test_namespace_narrows_after_its_first_field(
    vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory
) -> None:
    """An alias binds to one table, so its second field comes only from that table."""

    engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

    _feed(engine, "SELECT u.")

    assert _rules(engine) == schema.get_all_fields()

    _feed(engine, "email, u.")

    assert _rules(engine) == {"id", "first_name", "last_name", "email"}

def test_from_offers_only_required_tables(
    vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory
) -> None:
    engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

    _feed(engine, "SELECT email FROM ")

    assert _rules(engine) == {"users"}

def test_ambiguous_field_offers_both_tables(
    vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory
) -> None:
    """`title` is on posts and comments, so the FROM clause may pick either."""

    engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

    _feed(engine, "SELECT title FROM ")

    assert _rules(engine) == {"posts", "comments"}

def test_join_is_offered_only_along_foreign_keys(
    vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory
) -> None:
    engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

    _feed(engine, "SELECT email, title FROM users ")

    # Every join type is on offer, and nothing else at this point.
    assert _rules(engine) == {"INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN"}

    _feed(engine, "INNER JOIN ")

    assert _rules(engine) == {"posts", "comments"}

def test_on_clause_is_fully_determined(
    vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory
) -> None:
    """Once the join target is chosen, the ON columns are forced."""

    engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

    _feed(engine, "SELECT email, title FROM users INNER JOIN posts ON ")

    assert _rules(engine) == {"users.id"}

    _feed(engine, "users.id = ")

    assert _rules(engine) == {"posts.user_id"}
