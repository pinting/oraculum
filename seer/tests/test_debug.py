"""Debug tracing.

The whole resolver state is printed after every operation that modifies a
`Context`, under a heading naming what was applied.
"""

from __future__ import annotations

import io

import pytest

from src import debug
from src.context import Context
from src.relationships import JoinType, Neighbor
from src.schema import Schema

@pytest.fixture(autouse=True)
def quiet():
    """Tracing is global, so make sure a test never leaks it into the next."""

    yield

    debug.disable()

@pytest.fixture
def stream() -> io.StringIO:
    buffer = io.StringIO()

    debug.enable(buffer)

    return buffer

def _neighbor(ctx: Context, table: str) -> Neighbor:
    matches = [n for n in ctx.get_joinable_neighbors() if n.table == table]

    assert matches

    return matches[0]

class TestSwitch:
    def test_off_by_default(self) -> None:
        assert not debug.is_enabled()

    def test_enable_and_disable(self) -> None:
        buffer = io.StringIO()

        debug.enable(buffer)

        assert debug.is_enabled()

        debug.trace("op", "body")

        assert "body" in buffer.getvalue()

        debug.disable()

        assert not debug.is_enabled()

        debug.trace("op", "ignored")

        assert "ignored" not in buffer.getvalue()

    def test_silent_tracing_does_not_render(self) -> None:
        """`Root.__str__` runs a sympy simplification, so it must stay lazy."""

        class Exploding:
            def __str__(self) -> str:
                raise AssertionError("rendered while tracing was off")

        debug.disable()
        debug.trace("op", Exploding())

class TestFormat:
    def test_heading_names_the_operation(self, stream: io.StringIO) -> None:
        debug.trace("use_field(email)", "body")

        lines: list[str] = stream.getvalue().splitlines()

        assert lines[1].startswith("── use_field(email) ")
        assert len(lines[1]) == debug.WIDTH
        assert lines[2] == "body"

    def test_long_heading_is_not_truncated(self, stream: io.StringIO) -> None:
        label: str = "join_table(" + "x" * 100 + ")"

        debug.trace(label, "body")

        assert label in stream.getvalue()

class TestContextTracing:
    def test_every_modifying_operation_traces(
        self, schema: Schema, stream: io.StringIO
    ) -> None:
        ctx: Context = Context(schema)

        ctx.set_current_namespace("c")
        ctx.use_field("post_id")
        ctx.enter_from()
        ctx.use_table("comments c")

        headings: list[str] = [
            line for line in stream.getvalue().splitlines() if line.startswith("── ")
        ]

        assert len(headings) == 4
        assert headings[0].startswith("── set_current_namespace(c) ")
        assert headings[1].startswith("── use_field(c.post_id) ")
        assert headings[2].startswith("── enter_from() ")
        assert headings[3].startswith("── use_table(comments c) ")

    def test_label_is_taken_before_the_call(
        self, schema: Schema, stream: io.StringIO
    ) -> None:
        """`use_field` consumes the namespace, so the label must predate it."""

        ctx: Context = Context(schema)

        ctx.set_current_namespace("u")
        ctx.use_field("email")

        assert "use_field(u.email)" in stream.getvalue()

    def test_join_label_is_the_sql_clause(
        self, schema: Schema, stream: io.StringIO
    ) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")
        ctx.use_field("title")
        ctx.use_table("users")
        ctx.join_table(_neighbor(ctx, "posts"), JoinType.LEFT)

        assert "join_table(LEFT JOIN posts ON users.id = posts.user_id)" in stream.getvalue()

    def test_body_is_the_state_block(self, schema: Schema, stream: io.StringIO) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")

        assert str(ctx) in stream.getvalue()

    def test_queries_do_not_trace(self, schema: Schema, stream: io.StringIO) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")

        before: int = len(stream.getvalue())

        ctx.get_fields()
        ctx.get_required_tables()
        ctx.get_excluded_tables()
        ctx.is_satisfied()
        ctx.copy()

        assert len(stream.getvalue()) == before

    def test_a_whole_statement_stays_readable(
        self, schema: Schema, stream: io.StringIO
    ) -> None:
        """Selectors only fire on accepting cursors, so the volume is small."""

        ctx: Context = Context(schema)

        ctx.use_field("email")
        ctx.use_field("title")
        ctx.use_table("users")
        ctx.join_table(_neighbor(ctx, "posts"))

        headings: list[str] = [
            line for line in stream.getvalue().splitlines() if line.startswith("── ")
        ]

        assert len(headings) == 4
