"""`Context` -- the generation state built on `Conflicts` and `Relationships`.

Covers both phases the experiment models and the boundary between them, plus
the copy-on-write cloning the engine depends on.
"""

from __future__ import annotations

from src.context import Context
from src.relationships import JoinType, Neighbor
from src.schema import Schema

def _neighbor(ctx: Context, table: str) -> Neighbor:
    matches = [n for n in ctx.get_joinable_neighbors() if n.table == table]

    assert matches, f"{table} is not joinable from {ctx.get_head()}"

    return matches[0]

class TestFieldPhase:
    def test_starts_satisfied(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        assert ctx.is_satisfied()
        assert ctx.get_required_tables() == []
        assert ctx.get_fields() == [
            "body", "email", "first_name", "id", "last_name", "post_id", "title", "user_id",
        ]

    def test_fields_are_sorted(self, schema: Schema) -> None:
        """Expansion order has to be reproducible, so sets never escape."""

        ctx: Context = Context(schema)

        assert ctx.get_fields() == sorted(ctx.get_fields())

    def test_global_field_requires_its_table(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        assert ctx.use_field("email") is True
        assert ctx.get_required_tables() == ["users"]
        assert not ctx.is_satisfied()

    def test_namespace_is_consumed_by_use_field(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.set_current_namespace("c")

        assert ctx.get_current_namespace() == "c"

        ctx.use_field("post_id")

        assert ctx.get_current_namespace() == ""
        assert ctx.get_required_tables() == ["comments c"]

    def test_unknown_namespace_offers_every_field(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.set_current_namespace("x")

        assert set(ctx.get_fields()) == schema.get_all_fields()

    def test_namespace_narrows_after_its_first_field(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.set_current_namespace("u")
        ctx.use_field("email")
        ctx.set_current_namespace("u")

        assert ctx.get_fields() == ["email", "first_name", "id", "last_name"]

    def test_excluded_fields_are_reported(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")
        ctx.use_field("post_id")

        assert "id" in ctx.get_excluded_fields()

class TestPhaseBoundary:
    def test_join_graph_does_not_exist_before_from(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")

        assert ctx.relationships is None
        assert ctx.get_joinable_neighbors() == ()
        assert ctx.get_head() is None

    def test_enter_from_builds_the_graph(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.set_current_namespace("c")
        ctx.use_field("post_id")
        ctx.enter_from()

        assert ctx.relationships is not None
        assert "comments c" in ctx.relationships.graph.nodes()

    def test_enter_from_is_idempotent(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")
        ctx.enter_from()

        first = ctx.relationships

        ctx.enter_from()

        assert ctx.relationships is first

class TestTablePhase:
    def test_use_table_satisfies_and_sets_the_head(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")

        assert ctx.use_table("users") is True
        assert ctx.get_head() == "users"
        assert ctx.is_satisfied()

    def test_table_not_required_is_refused(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")

        assert ctx.use_table("posts") is False
        assert ctx.get_head() is None

    def test_join_satisfies_a_required_neighbor(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")
        ctx.use_field("title")

        assert set(ctx.get_required_tables()) == {"users", "posts", "comments"}

        assert ctx.use_table("users") is True

        assert ctx.join_table(_neighbor(ctx, "posts")) is True
        assert ctx.is_satisfied()

    def test_join_extends_the_reach(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")
        ctx.set_current_namespace("c")
        ctx.use_field("post_id")
        ctx.use_table("users")

        assert ctx.join_table(_neighbor(ctx, "comments c")) is True
        assert ctx.is_satisfied()

    def test_unreachable_neighbor_is_refused(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")
        ctx.use_table("users")

        assert ctx.join_table(Neighbor("posts", "wrong.a", "wrong.b")) is False

    def test_join_before_from_is_refused(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        assert ctx.join_table(Neighbor("posts", "a", "b")) is False

    def test_join_type_is_recorded(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")
        ctx.use_field("title")
        ctx.use_table("users")
        ctx.join_table(_neighbor(ctx, "posts"), JoinType.LEFT)

        assert str(ctx.relationships) == "users LEFT JOIN posts ON users.id = posts.user_id"

class TestCopy:
    def test_field_state_is_isolated(self, schema: Schema) -> None:
        ctx: Context = Context(schema)
        clone: Context = ctx.copy()

        clone.use_field("email")

        assert clone.get_required_tables() == ["users"]
        assert ctx.get_required_tables() == []

    def test_namespace_state_is_isolated(self, schema: Schema) -> None:
        ctx: Context = Context(schema)
        clone: Context = ctx.copy()

        clone.set_current_namespace("c")
        clone.use_field("post_id")

        assert clone.get_required_tables() == ["comments c"]
        assert ctx.get_required_tables() == []

    def test_join_graph_is_isolated(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")
        ctx.use_field("title")
        ctx.use_table("users")

        clone: Context = ctx.copy()

        clone.join_table(_neighbor(clone, "posts"))

        assert clone.is_satisfied()
        assert not ctx.is_satisfied()
        assert "posts" in ctx.relationships.graph.nodes()

    def test_phase_boundary_is_isolated(self, schema: Schema) -> None:
        ctx: Context = Context(schema)
        clone: Context = ctx.copy()

        clone.enter_from()

        assert clone.relationships is not None
        assert ctx.relationships is None

class TestDisplay:
    """`Context.__str__` is the state block the experiment's TUI reprints."""

    def test_block_has_the_experiment_layout(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")

        assert str(ctx).splitlines() == [
            "Satisfied        = False",
            "Selected fields  = email",
            "Excluded fields  = ",
            "Root tables      = users",
            "Scopes tables    = ",
            "Excluded tables  = ",
            "Used references  = ",
        ]

    def test_initial_state(self, schema: Schema) -> None:
        lines: list[str] = str(Context(schema)).splitlines()

        assert lines[0] == "Satisfied        = True"
        assert lines[3] == "Root tables      = True"

    def test_scopes_and_references_are_reported(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")
        ctx.set_current_namespace("c")
        ctx.use_field("post_id")
        ctx.use_table("users")
        ctx.join_table(_neighbor(ctx, "comments c"))

        block: str = str(ctx)

        assert "Selected fields  = email, c.post_id" in block
        assert "Scopes tables    = c = 1" in block
        assert (
            "Used references  = users INNER JOIN comments AS c ON users.id = c.user_id"
            in block
        )
        assert "Satisfied        = True" in block

    def test_root_is_rendered_as_dnf(self, schema: Schema) -> None:
        """An ambiguous field leaves a disjunction, simplified by sympy."""

        ctx: Context = Context(schema)

        ctx.use_field("title")

        line: str = [
            row for row in str(ctx).splitlines() if row.startswith("Root tables")
        ][0]

        assert "posts" in line and "comments" in line
        assert "|" in line

    def test_repr_is_short(self, schema: Schema) -> None:
        ctx: Context = Context(schema)

        ctx.use_field("email")

        assert repr(ctx) == "Context(required=['users'])"
