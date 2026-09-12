"""The WHERE clause: a virtual table, and conditions typed against it.

    ... FROM <entry> [, <entry>]* WHERE <filters> ;
    <filters>   := <predicate> [(AND | OR) <predicate>]*
    <predicate> := [NOT] (<condition> | "(" <filters> ")")
    <condition> := <operand> <operator> <operand | literal>
                 | <operand> IS [NOT] NULL

Two things are being enforced at once and the rejections separate them. The
**relation** decides which columns exist at all: only what the FROM clause
placed, qualified by the node's reference name, and bare only where one node
supplies the name. The **type** then decides which operators that column takes
and what may face it across one.

This file parses a schema of its own rather than the shared fixture, because
the interesting gates need a nullable column, a temporal one and a boolean one,
and the fixture deliberately has none of them.
"""

from __future__ import annotations

import pytest

import kernel as kl

from src.engine import Engine
from src.factory import IndexFactory
from src.graph import COMMA, IDENTIFIER, LPAREN, RPAREN, WHITESPACE, root
from src.operators import LITERALS, TypeClass
from src.schema import Schema, parse_schema

from .helpers import drive

# `id` is ambiguous across both tables and `email`, `title` are not; `verified`
# is the only boolean, `created_at` and `published_at` the only temporals, and
# both of those are the only columns that may be null.
SCHEMA: str = """
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    verified BOOLEAN,
    created_at TIMESTAMP
);

CREATE TABLE posts (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    published_at TIMESTAMP
);
"""

JOIN: str = (
    "SELECT email, title FROM users INNER JOIN posts ON users.id = posts.user_id"
)

@pytest.fixture(scope="module")
def schema() -> Schema:
    parsed: Schema | None = parse_schema(SCHEMA)

    assert parsed is not None

    return parsed

ACCEPTED: list[str] = [
    # the clause is optional
    "SELECT email FROM users;",
    # a literal of the operand's class
    "SELECT email FROM users WHERE email = 'bob@example.com';",
    "SELECT email FROM users WHERE users.id > 10;",
    "SELECT email FROM users WHERE users.id = -1;",
    "SELECT email FROM users WHERE created_at >= '2024-01-31';",
    "SELECT email FROM users WHERE created_at < '2024-01-31 12:30:00';",
    "SELECT email FROM users WHERE verified = TRUE;",
    # text alone may be matched against a pattern
    "SELECT email FROM users WHERE email LIKE 'a%';",
    "SELECT email FROM users WHERE email NOT LIKE 'a%';",
    # only a nullable column may be tested for null
    "SELECT email FROM users WHERE created_at IS NULL;",
    "SELECT email FROM users WHERE created_at IS NOT NULL;",
    # an alias qualifies the columns it brought in
    "SELECT u.email FROM users AS u WHERE u.email = 'a';",
    "SELECT u.email FROM users AS u WHERE email = 'a';",
    # column against column, within one class, across a join
    JOIN + " WHERE users.id = posts.user_id;",
    JOIN + " WHERE created_at < published_at;",
    # a bare name that only one side of the join supplies
    JOIN + " WHERE email = title;",
    # the connectives, negation and nesting
    "SELECT email FROM users WHERE email = 'a' AND users.id > 1;",
    "SELECT email FROM users WHERE email = 'a' OR email = 'b';",
    "SELECT email FROM users WHERE NOT email = 'a';",
    "SELECT email FROM users WHERE (email = 'a' OR email = 'b') AND NOT users.id = 1;",
    "SELECT email FROM users WHERE ( email = 'a' AND users.id = 1 ) OR verified = FALSE;",
    "SELECT email FROM users WHERE ((email = 'a' OR email = 'b') AND users.id = 1);",
]

REJECTED: list[str] = [
    # -- the relation: a column the FROM clause never placed ---------------
    "SELECT email FROM users WHERE title = 'x';",
    "SELECT email FROM users WHERE posts.title = 'x';",
    # the qualifier is the alias, not the table it stands for
    "SELECT u.email FROM users AS u WHERE users.email = 'x';",
    # both sides of the join carry `id`, so the bare spelling is ambiguous
    JOIN + " WHERE id = 1;",
    # -- the type: a literal of the wrong class ----------------------------
    "SELECT email FROM users WHERE users.id = 'x';",
    "SELECT email FROM users WHERE email < 5;",
    "SELECT email FROM users WHERE created_at = 5;",
    "SELECT email FROM users WHERE verified = 1;",
    # -- the type: an operator the class does not admit --------------------
    "SELECT email FROM users WHERE users.id LIKE 'a%';",
    "SELECT email FROM users WHERE verified < TRUE;",
    # -- the type: two columns of different classes ------------------------
    "SELECT email FROM users WHERE email = users.id;",
    JOIN + " WHERE created_at < title;",
    # -- nullability -------------------------------------------------------
    "SELECT email FROM users WHERE email IS NULL;",
    # a primary key is never null, however the column was written
    "SELECT email FROM users WHERE users.id IS NOT NULL;",
    # -- a condition that says nothing -------------------------------------
    "SELECT email FROM users WHERE email = email;",
    "SELECT email FROM users WHERE email = users.email;",
    # -- still a statement -------------------------------------------------
    "SELECT email FROM users WHERE email = 'a'",
    "SELECT email FROM users WHERE;",
    "SELECT email FROM users WHERE email;",
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

# The separator patterns, which are on offer nearly everywhere and say nothing
# about which alternative the modelling picked.
PATTERNS: frozenset[str] = frozenset({IDENTIFIER, WHITESPACE, COMMA, LPAREN, RPAREN})

def _feed(engine: Engine, text: str) -> None:
    """Consume `text`, taking the longest legal token at each step."""

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

def _rules(engine: Engine) -> set[str]:
    return {head.rule for head in engine.heads if head.rule not in PATTERNS}

ORDERING: set[str] = {"=", "!=", "<", "<=", ">", ">="}

class TestOnOffer:
    def test_the_relation_bounds_the_operands(
        self, vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory
    ) -> None:
        """Only what the FROM clause placed, in both of its spellings."""

        engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

        _feed(engine, "SELECT email FROM users WHERE ")

        assert _rules(engine) == {
            "NOT",
            "created_at", "email", "id", "verified",
            "users.created_at", "users.email", "users.id", "users.verified",
        }

    def test_a_join_widens_it(
        self, vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory
    ) -> None:
        """Both sides are in the relation, and `id` loses its bare spelling."""

        engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

        _feed(engine, JOIN + " WHERE ")

        offered: set[str] = _rules(engine)

        assert "posts.title" in offered and "users.email" in offered
        assert "title" in offered and "email" in offered
        assert "users.id" in offered and "posts.id" in offered
        assert "id" not in offered

    def test_the_type_fixes_the_operators(
        self, vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory
    ) -> None:
        """The WHERE analogue of the ON clause being forced by its target."""

        engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

        _feed(engine, "SELECT email FROM users WHERE users.id ")

        # Numeric: ordered, never matched, and a primary key is never null.
        assert _rules(engine) == ORDERING

    def test_text_adds_matching_and_null_tests(
        self, vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory
    ) -> None:
        engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

        _feed(engine, "SELECT email FROM users WHERE created_at ")

        assert _rules(engine) == ORDERING | {"IS NULL", "IS NOT NULL"}

    def test_the_right_hand_side_is_the_left_hand_class(
        self, vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory
    ) -> None:
        engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

        _feed(engine, JOIN + " WHERE users.created_at = ")

        offered: set[str] = _rules(engine)

        # The other temporal column in both spellings, plus a temporal literal,
        # and nothing else - the left operand itself is dropped however it is
        # written, and no column of another class is reachable.
        assert offered == {
            "posts.published_at",
            "published_at",
            LITERALS[TypeClass.TEMPORAL],
        }

    def test_a_boolean_takes_only_its_own_literal(
        self, vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory
    ) -> None:
        engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

        _feed(engine, "SELECT email FROM users WHERE verified = ")

        # No other boolean column exists, so the pattern is all that is left.
        assert _rules(engine) == {LITERALS[TypeClass.BOOLEAN]}

class TestState:
    def test_conditions_reach_the_context(
        self, vocabulary: kl.Vocabulary, schema: Schema, factory: IndexFactory
    ) -> None:
        """A condition is committed on its last token, like a join clause."""

        engine: Engine = Engine(vocabulary, schema, root(), factory=factory)

        _feed(engine, "SELECT email FROM users WHERE email = 'a' AND users.id > 1")

        recorded: set[tuple[str, ...]] = {
            head.payload.ctx.get_used_filters() for head in engine.heads
        }

        assert ("email = 'a'", "users.id > 1") in recorded
