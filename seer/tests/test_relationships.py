"""`Relationships` - the foreign key join graph.

`JoinGraph` is the vocabulary of this module over SageMath's `Graph`, so these
cover both the edges built from a schema and what merging a neighbour into the
head does to them.
"""

from __future__ import annotations

from src.relationships import (
    EdgeLabel,
    FieldRef,
    JoinGraph,
    JoinType,
    Neighbor,
    Relationships,
    reference_name,
)
from src.schema import Schema

def _label(a: str, b: str) -> EdgeLabel:
    return EdgeLabel(src=FieldRef(a, f"{a}.x"), dst=FieldRef(b, f"{b}.y"))

class TestJoinGraph:
    def test_edges_are_undirected(self) -> None:
        graph: JoinGraph = JoinGraph([("a", "b", _label("a", "b"))])

        assert graph.nodes() == ["a", "b"]
        assert [n for n, _ in graph.edges("a")] == ["b"]
        assert [n for n, _ in graph.edges("b")] == ["a"]
        assert "a" in graph and "z" not in graph

    def test_multi_edges_are_kept(self) -> None:
        graph: JoinGraph = JoinGraph([
            ("a", "b", _label("a", "b")),
            ("a", "b", EdgeLabel(src=FieldRef("a", "a.p"), dst=FieldRef("b", "b.q"))),
        ])

        assert len(graph.edges("a")) == 2

    def test_merge_unions_the_neighbourhood(self) -> None:
        graph: JoinGraph = JoinGraph([
            ("a", "b", _label("a", "b")),
            ("b", "c", _label("b", "c")),
        ])

        graph.merge_vertices("a", "b")

        assert "b" not in graph
        assert [n for n, _ in graph.edges("a")] == ["c"]
        assert [n for n, _ in graph.edges("c")] == ["a"]

    def test_merge_drops_the_loop(self) -> None:
        graph: JoinGraph = JoinGraph([("a", "b", _label("a", "b"))])

        graph.merge_vertices("a", "b")

        assert graph.edges("a") == []

    def test_merge_is_a_noop_for_unknown_or_self(self) -> None:
        graph: JoinGraph = JoinGraph([("a", "b", _label("a", "b"))])

        graph.merge_vertices("a", "a")
        graph.merge_vertices("a", "zzz")

        assert graph.nodes() == ["a", "b"]

    def test_copy_is_isolated(self) -> None:
        graph: JoinGraph = JoinGraph([("a", "b", _label("a", "b"))])
        clone: JoinGraph = graph.copy()

        clone.merge_vertices("a", "b")

        assert "b" not in clone
        assert "b" in graph

class TestEdgeLabel:
    def test_orient_points_away_from_the_head(self) -> None:
        label: EdgeLabel = EdgeLabel(
            src=FieldRef("posts", "posts.user_id"),
            dst=FieldRef("users", "users.id"),
        )

        assert label.orient("posts", "users") == Neighbor("users", "posts.user_id", "users.id")
        assert label.orient("users", "posts") == Neighbor("posts", "users.id", "posts.user_id")

class TestReferenceName:
    def test_alias_wins(self) -> None:
        assert reference_name("comments c") == "c"
        assert reference_name("comments") == "comments"

class TestRelationships:
    def test_nodes_include_aliases(self, schema: Schema) -> None:
        relationships: Relationships = Relationships(schema, {"comments c"})

        assert relationships.graph.nodes() == ["comments", "comments c", "posts", "users"]

    def test_neighbors_follow_foreign_keys(self, schema: Schema) -> None:
        relationships: Relationships = Relationships(schema, ())

        relationships.use_table("users")

        assert {n.table for n in relationships.get_joinable_neighbors()} == {"posts", "comments"}

    def test_on_clause_uses_the_alias(self, schema: Schema) -> None:
        relationships: Relationships = Relationships(schema, {"comments c"})

        relationships.use_table("users")

        aliased = [n for n in relationships.get_joinable_neighbors() if n.table == "comments c"]

        assert len(aliased) == 1
        assert aliased[0] == Neighbor("comments c", "users.id", "c.user_id")
        assert aliased[0].format() == "INNER JOIN comments AS c ON users.id = c.user_id"

    def test_excluded_neighbors_are_hidden(self, schema: Schema) -> None:
        relationships: Relationships = Relationships(schema, ())

        relationships.use_table("users")

        neighbors = relationships.get_joinable_neighbors(frozenset({"comments"}))

        assert {n.table for n in neighbors} == {"posts"}

    def test_join_merges_and_extends_the_reach(self, schema: Schema) -> None:
        """users cannot reach comments via post_id until posts is joined."""

        relationships: Relationships = Relationships(schema, ())

        relationships.use_table("users")

        posts = [n for n in relationships.get_joinable_neighbors() if n.table == "posts"][0]

        relationships.join_table(posts)

        pairs = {(n.src_field, n.dst_field) for n in relationships.get_joinable_neighbors()}

        assert ("posts.id", "comments.post_id") in pairs
        assert ("users.id", "comments.user_id") in pairs

    def test_used_references_render_sql(self, schema: Schema) -> None:
        relationships: Relationships = Relationships(schema, {"comments c"})

        relationships.use_table("users")

        neighbor = [n for n in relationships.get_joinable_neighbors() if n.table == "comments c"][0]

        relationships.join_table(neighbor, JoinType.LEFT)

        assert str(relationships) == "users LEFT JOIN comments AS c ON users.id = c.user_id"

    def test_used_nodes_are_structural(self, schema: Schema) -> None:
        """The SQL rendering is for reading; the node names are for the relation."""

        relationships: Relationships = Relationships(schema, {"comments c"})

        relationships.use_table("users")

        neighbor = [n for n in relationships.get_joinable_neighbors() if n.table == "comments c"][0]

        relationships.join_table(neighbor, JoinType.LEFT)

        assert relationships.get_used_nodes() == ("users", "comments c")

    def test_used_nodes_span_entries(self, schema: Schema) -> None:
        relationships: Relationships = Relationships(schema, ())

        relationships.use_table("users")
        relationships.use_table("posts")

        assert relationships.get_used_nodes() == ("users", "posts")

    def test_neighbors_are_ordered(self, schema: Schema) -> None:
        relationships: Relationships = Relationships(schema, ())

        relationships.use_table("users")

        neighbors = relationships.get_joinable_neighbors()

        assert list(neighbors) == sorted(neighbors)

    def test_no_head_means_no_neighbors(self, schema: Schema) -> None:
        relationships: Relationships = Relationships(schema, ())

        assert relationships.get_joinable_neighbors() == ()
        assert relationships.join_table(Neighbor("posts", "a", "b")) is False

    def test_copy_is_isolated(self, schema: Schema) -> None:
        relationships: Relationships = Relationships(schema, ())

        relationships.use_table("users")

        clone: Relationships = relationships.copy()
        posts = [n for n in clone.get_joinable_neighbors() if n.table == "posts"][0]

        clone.join_table(posts)

        assert "posts" not in clone.graph
        assert "posts" in relationships.graph
        assert relationships.get_used_references() == ("users",)
        assert relationships.get_used_nodes() == ("users",)
        assert clone.get_used_nodes() == ("users", "posts")
