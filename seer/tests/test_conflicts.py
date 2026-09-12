"""`Conflicts` - the facade over `Root` and `Scopes`."""

from __future__ import annotations

from src.conflicts import Conflicts
from src.schema import Schema

class TestFieldSelection:
    def test_starts_empty_and_satisfied(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)

        assert conflicts.is_satisfied()
        assert conflicts.get_required_tables() == frozenset()
        assert conflicts.get_used_fields() == ()

    def test_unqualified_field_goes_to_root(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)

        assert conflicts.use_field("", "email") is True
        assert conflicts.get_required_tables() == {"users"}
        assert conflicts.get_used_fields() == ("email",)

    def test_qualified_field_goes_to_a_scope(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)

        assert conflicts.use_field("c", "post_id") is True
        assert conflicts.get_required_tables() == {"comments c"}
        assert conflicts.get_used_fields() == ("c.post_id",)
        assert conflicts.scopes.names() == ["c"]

    def test_unknown_scope_offers_every_field(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)

        assert conflicts.get_fields("nobody") == conflicts.get_all_fields()
        assert conflicts.get_excluded_fields("nobody") == frozenset()

    def test_scope_narrows_after_its_first_field(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)

        conflicts.use_field("u", "email")

        assert conflicts.get_fields("u") == {"id", "first_name", "last_name", "email"}

    def test_root_and_scopes_are_independent(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)

        conflicts.use_field("", "email")
        conflicts.use_field("p", "title")

        assert conflicts.get_required_tables() == {"users", "posts p", "comments p"}

    def test_rejected_field_is_not_recorded(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)

        assert conflicts.use_field("", "nope") is False
        assert conflicts.get_used_fields() == ()

class TestTableSelection:
    def test_bare_node_goes_to_root(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)

        conflicts.use_field("", "email")

        assert conflicts.use_table("users") is True
        assert conflicts.is_satisfied()

    def test_aliased_node_goes_to_its_scope(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)

        conflicts.use_field("c", "post_id")

        assert conflicts.use_table("comments c") is True
        assert conflicts.is_satisfied()

    def test_alias_satisfies_the_root_too(self, schema: Schema) -> None:
        """An aliased table is still present, so root constraints naming it hold."""

        conflicts: Conflicts = Conflicts(schema)

        conflicts.use_field("", "post_id")
        conflicts.use_field("c", "post_id")

        assert conflicts.get_required_tables() == {"comments", "comments c"}

        assert conflicts.use_table("comments c") is True
        assert conflicts.is_satisfied()

    def test_wrong_table_for_an_alias(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)

        conflicts.use_field("u", "email")

        assert conflicts.use_table("posts u") is False
        assert not conflicts.is_satisfied()

    def test_unknown_scope(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)

        assert conflicts.use_table("users x") is False

class TestCopy:
    def test_branches_are_isolated(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)
        clone: Conflicts = conflicts.copy()

        clone.use_field("", "email")

        assert clone.get_required_tables() == {"users"}
        assert conflicts.get_required_tables() == frozenset()

    def test_scopes_are_isolated(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)

        conflicts.use_field("c", "title")

        clone: Conflicts = conflicts.copy()

        clone.use_field("c", "post_id")

        assert clone.get_required_tables() == {"comments c"}
        assert conflicts.get_required_tables() == {"posts c", "comments c"}

    def test_used_fields_do_not_leak(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)
        clone: Conflicts = conflicts.copy()

        clone.use_field("", "email")

        assert conflicts.get_used_fields() == ()
        assert clone.get_used_fields() == ("email",)

class TestDisplay:
    def test_str_reports_the_state(self, schema: Schema) -> None:
        conflicts: Conflicts = Conflicts(schema)

        conflicts.use_field("", "email")

        rendered: str = str(conflicts)

        assert "Satisfied        = False" in rendered
        assert "Selected fields  = email" in rendered
        assert "Root tables      = users" in rendered
