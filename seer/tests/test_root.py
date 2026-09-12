"""`Root` -- the GF(2) mutual exclusion resolver.

The running product over SageMath's `BooleanPolynomialRing`: selecting a field
multiplies its mutual exclusion constraint in, and the questions the FROM
clause asks are substitutions into what that product became.
"""

from __future__ import annotations

from src.root import Root

TABLES: dict[str, list[str]] = {
    "users": ["id", "first_name", "email"],
    "posts": ["id", "user_id", "title"],
    "comments": ["id", "user_id", "post_id", "title"],
}

class TestRoot:
    def test_starts_satisfied_with_no_requirements(self) -> None:
        root: Root = Root(TABLES)

        assert root.is_satisfied()
        assert root.get_required_tables() == frozenset()
        assert root.get_fields() == frozenset(
            {"id", "first_name", "email", "user_id", "title", "post_id"}
        )
        assert str(root) == "True"

    def test_unique_field_pins_one_table(self) -> None:
        root: Root = Root(TABLES)

        assert root.use_field("email") is True
        assert root.get_required_tables() == {"users"}
        assert not root.is_satisfied()
        assert str(root) == "users"

    def test_ambiguous_field_allows_either_table(self) -> None:
        root: Root = Root(TABLES)

        root.use_field("title")

        assert root.get_required_tables() == {"posts", "comments"}

    def test_exactly_one_semantics(self) -> None:
        """`title` is on posts and comments, so both cannot be selected."""

        root: Root = Root(TABLES)

        root.use_field("title")

        assert root.use_table("posts") is True
        assert root.use_table("comments") is False

    def test_fields_from_two_tables_require_both(self) -> None:
        root: Root = Root(TABLES)

        root.use_field("email")
        root.use_field("post_id")

        assert root.get_required_tables() == {"users", "comments"}

        assert root.use_table("comments") is True
        assert root.get_required_tables() == {"users"}

        assert root.use_table("users") is True
        assert root.is_satisfied()

    def test_excluded_fields_are_the_complement(self) -> None:
        root: Root = Root(TABLES)

        root.use_field("email")
        root.use_field("post_id")

        assert "id" in root.get_excluded_fields()
        assert root.get_excluded_fields() & root.get_fields() == frozenset()

    def test_excluded_tables_track_use(self) -> None:
        root: Root = Root(TABLES)

        root.use_field("title")
        root.use_table("posts")

        excluded: frozenset[str] = root.get_excluded_tables()

        assert "posts" in excluded
        assert "comments" in excluded
        assert root.get_used_tables() == {"posts"}

    def test_contradiction_is_refused_without_mutating(self) -> None:
        root: Root = Root(TABLES)

        root.use_field("title")
        root.use_table("posts")

        before: frozenset[str] = root.get_required_tables()
        used: frozenset[str] = root.get_used_tables()

        # `title` is already supplied by posts, so comments would collapse it.
        assert root.use_table("comments") is False
        assert root.get_required_tables() == before
        assert root.get_used_tables() == used

    def test_redundant_table_is_allowed(self) -> None:
        """A table no field needs does not contradict anything on its own.

        It is the syntax graph that never offers such a table, because it only
        ever lists the required ones.
        """

        root: Root = Root(TABLES)

        root.use_field("email")

        assert root.use_table("posts") is True
        assert root.get_used_tables() == {"posts"}

    def test_unknown_names(self) -> None:
        root: Root = Root(TABLES)

        assert root.use_field("nope") is False
        assert root.use_table("nope") is False

    def test_copy_shares_store_but_not_state(self) -> None:
        root: Root = Root(TABLES)
        clone: Root = root.copy()

        clone.use_field("email")

        assert clone.get_required_tables() == {"users"}
        assert root.get_required_tables() == frozenset()
        assert root.is_satisfied()

    def test_str_renders_dnf(self) -> None:
        root: Root = Root(TABLES)

        root.use_field("title")

        rendered: str = str(root)

        assert "posts" in rendered and "comments" in rendered
        assert "|" in rendered
