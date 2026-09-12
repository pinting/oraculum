"""The sqlglot backed schema parser.

`TestBasicCases` are the shapes a schema is expected to come in at all;
`TestBeyondLineScanning` are the ones a parser has to be a real parser to
read, rather than a scanner working a line at a time.
"""

from __future__ import annotations

from src.schema import Reference, Schema, Type, parse_schema

class TestBasicCases:

    def test_parse_simple_schema(self) -> None:
        schema = parse_schema("""
CREATE TABLE users (
    id INTEGER,
    email TEXT
);""")

        assert schema is not None
        assert len(schema.tables) == 1
        assert list(schema.tables["users"].fields) == ["id", "email"]

    def test_parse_nested_parens(self) -> None:
        schema = parse_schema("""
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    total DECIMAL(10, 2),
    status TEXT DEFAULT 'pending'
);""")

        assert schema is not None
        assert list(schema.tables["orders"].fields) == ["id", "user_id", "total", "status"]

    def test_parse_multiple_tables(self) -> None:
        schema = parse_schema("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    total DECIMAL(10, 2),
    status TEXT DEFAULT 'pending'
);""")

        assert schema is not None
        assert len(schema.tables) == 2
        assert schema.get_fields() == {
            "users": ["id", "name", "email"],
            "orders": ["id", "user_id", "total", "status"],
        }

class TestBeyondLineScanning:
    def test_single_line_table(self) -> None:
        """Every column is on one line, so a line at a time sees only the first."""

        schema = parse_schema("CREATE TABLE t (a INT, b INT, c INT);")

        assert schema is not None
        assert list(schema.tables["t"].fields) == ["a", "b", "c"]

    def test_constraints_are_captured(self) -> None:
        schema = parse_schema("""
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    nickname VARCHAR(64)
);""")

        assert schema is not None

        table = schema.tables["users"]

        assert table.primary_key == "id"
        assert table.unique == ["email"]
        assert table.fields["id"].is_primary_key
        assert table.fields["email"].is_unique
        assert not table.fields["email"].is_nullable
        assert table.fields["nickname"].is_nullable

    def test_types_and_lengths(self) -> None:
        schema = parse_schema("CREATE TABLE t (\n a VARCHAR(255),\n b BIGINT,\n c TEXT\n);")

        assert schema is not None

        fields = schema.tables["t"].fields

        assert fields["a"].type == Type("VARCHAR", 255)
        assert fields["b"].type == Type("BIGINT", None)
        assert str(fields["a"].type) == "VARCHAR(255)"
        assert str(fields["c"].type) == "TEXT"

    def test_references_are_captured(self) -> None:
        schema = parse_schema("""
CREATE TABLE users (id BIGINT PRIMARY KEY);
CREATE TABLE posts (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE
);""")

        assert schema is not None

        posts = schema.tables["posts"]

        assert posts.fields["user_id"].reference == Reference("users", "id")
        assert posts.fields["id"].reference is None
        assert [f.name for f in posts.references("users")] == ["user_id"]
        assert list(posts.references("nothing")) == []

    def test_identity_columns(self) -> None:
        """An identity column still parses as the primary key."""

        schema = parse_schema("""
CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL
);""")

        assert schema is not None
        assert schema.tables["users"].primary_key == "id"

class TestFailure:
    def test_empty_and_garbage_return_none(self) -> None:
        assert parse_schema("") is None
        assert parse_schema("SELECT 1;") is None
        assert parse_schema("this is not sql at all") is None

    def test_schema_is_falsy_when_empty(self) -> None:
        assert not Schema()

class TestViews:
    def test_get_fields_and_all_fields(self) -> None:
        schema = parse_schema("""
CREATE TABLE a (
    id INT,
    x INT
);
CREATE TABLE b (
    id INT,
    y INT
);""")

        assert schema is not None
        assert schema.get_fields() == {"a": ["id", "x"], "b": ["id", "y"]}
        assert schema.get_all_fields() == {"id", "x", "y"}
