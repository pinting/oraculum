"""`Scope` and `Scopes` -- alias resolution by set intersection."""

from __future__ import annotations

from src.scope import Scope
from src.scopes import Scopes, qualify, sql_name, unqualify

TABLES: dict[str, list[str]] = {
    "users": ["id", "first_name", "email"],
    "posts": ["id", "user_id", "title"],
    "comments": ["id", "user_id", "post_id", "title"],
}

class TestNodeNames:
    def test_qualify(self) -> None:
        assert qualify("users", "u") == "users u"
        assert qualify("users", "") == "users"

    def test_unqualify(self) -> None:
        assert unqualify("users u") == ("users", "u")
        assert unqualify("users") == ("users", "")

    def test_sql_name(self) -> None:
        assert sql_name("comments c") == "comments AS c"
        assert sql_name("comments") == "comments"

    def test_round_trip(self) -> None:
        for node in ["users", "users u", "comments c"]:
            assert qualify(*unqualify(node)) == node

class TestScope:
    def test_starts_with_every_field(self) -> None:
        scope: Scope = Scope(TABLES)

        assert scope.get_fields() == frozenset(
            {"id", "first_name", "email", "user_id", "title", "post_id"}
        )
        assert not scope.is_satisfied()

    def test_field_narrows_candidates(self) -> None:
        scope: Scope = Scope(TABLES)

        assert scope.use_field("email") is True
        assert scope.get_required_tables() == {"users"}
        assert scope.get_fields() == {"id", "first_name", "email"}
        assert scope.get_excluded_tables() == {"posts", "comments"}

    def test_conflicting_fields_are_rejected(self) -> None:
        scope: Scope = Scope(TABLES)

        assert scope.use_field("email") is True
        assert scope.use_field("title") is False
        assert scope.get_required_tables() == {"users"}

    def test_intersection_narrows_to_one(self) -> None:
        scope: Scope = Scope(TABLES)

        scope.use_field("title")

        assert scope.get_required_tables() == {"posts", "comments"}

        scope.use_field("post_id")

        assert scope.get_required_tables() == {"comments"}

    def test_unknown_field(self) -> None:
        scope: Scope = Scope(TABLES)

        assert scope.use_field("nope") is False
        assert scope.get_required_tables() == {"users", "posts", "comments"}

    def test_use_table_satisfies(self) -> None:
        scope: Scope = Scope(TABLES)

        scope.use_field("email")

        assert scope.use_table("posts") is False
        assert scope.use_table("users") is True
        assert scope.is_satisfied()
        assert scope.get_required_tables() == frozenset()

    def test_excluded_fields_are_the_complement(self) -> None:
        scope: Scope = Scope(TABLES)

        scope.use_field("email")

        assert scope.get_excluded_fields() == {"user_id", "title", "post_id"}

    def test_copy_is_isolated(self) -> None:
        scope: Scope = Scope(TABLES)
        clone: Scope = scope.copy()

        clone.use_field("email")

        assert clone.get_required_tables() == {"users"}
        assert scope.get_required_tables() == {"users", "posts", "comments"}

class TestScopes:
    def test_scope_is_created_on_first_field(self) -> None:
        scopes: Scopes = Scopes(TABLES)

        assert scopes.names() == []
        assert scopes.get_fields("u") is None

        assert scopes.use_field("u", "email") is True
        assert scopes.names() == ["u"]
        assert scopes.get_fields("u") == {"id", "first_name", "email"}

    def test_required_tables_are_qualified(self) -> None:
        scopes: Scopes = Scopes(TABLES)

        scopes.use_field("u", "email")
        scopes.use_field("c", "post_id")

        assert scopes.get_required_tables() == {"users u", "comments c"}

    def test_excluded_tables_are_qualified(self) -> None:
        scopes: Scopes = Scopes(TABLES)

        scopes.use_field("u", "email")

        assert scopes.get_excluded_tables() == {"posts u", "comments u"}

    def test_unknown_scope_operations(self) -> None:
        scopes: Scopes = Scopes(TABLES)

        assert scopes.use_table("missing", "users") is False
        assert scopes.get_excluded_fields("missing") is None
        assert "missing" not in scopes

    def test_is_satisfied_needs_every_scope(self) -> None:
        scopes: Scopes = Scopes(TABLES)

        assert scopes.is_satisfied()

        scopes.use_field("u", "email")

        assert not scopes.is_satisfied()

        assert scopes.use_table("u", "users") is True
        assert scopes.is_satisfied()

    def test_failed_first_field_leaves_no_scope(self) -> None:
        """The experiment registers the scope before narrowing it, so a failed
        first field leaves an empty scope behind that requires every table."""

        scopes: Scopes = Scopes(TABLES)

        assert scopes.use_field("u", "nope") is False
        assert scopes.names() == []
        assert scopes.get_required_tables() == frozenset()

    def test_copy_is_isolated(self) -> None:
        scopes: Scopes = Scopes(TABLES)

        scopes.use_field("u", "title")

        clone: Scopes = scopes.copy()

        clone.use_field("u", "post_id")

        assert clone.get_required_tables() == {"comments u"}
        assert scopes.get_required_tables() == {"posts u", "comments u"}
