"""`Relation` - the virtual table a finished FROM clause produces.

No engine and no kernel: the relation is built from a `Schema` and the node
names the clause placed, which is all `Context.enter_where` hands it. The two
questions worth pinning are the ones SQL leaves to a resolver - which qualifier
a column answers to, and when its bare name is ambiguous.
"""

from __future__ import annotations

from src.operators import TypeClass
from src.relation import Operand, Relation
from src.schema import Schema

def _texts(relation: Relation, kind: TypeClass | None = None) -> list[str]:
    return [operand.text for operand in relation.get_operands(kind)]

class TestConstruction:
    def test_one_table_offers_both_spellings(self, schema: Schema) -> None:
        relation: Relation = Relation(schema, ("users",))

        assert _texts(relation) == [
            "email", "first_name", "id", "last_name",
            "users.email", "users.first_name", "users.id", "users.last_name",
        ]

    def test_operands_are_ordered_by_spelling(self, schema: Schema) -> None:
        """Expansion has to be reproducible, so the order cannot be the schema's."""

        relation: Relation = Relation(schema, ("posts", "users"))

        assert _texts(relation) == sorted(_texts(relation))

    def test_nodes_are_kept_in_order(self, schema: Schema) -> None:
        relation: Relation = Relation(schema, ("users", "posts"))

        assert relation.get_nodes() == ("users", "posts")

    def test_repeated_nodes_collapse(self, schema: Schema) -> None:
        relation: Relation = Relation(schema, ("users", "users"))

        assert relation.get_nodes() == ("users",)
        assert _texts(relation).count("users.email") == 1

    def test_unknown_node_is_skipped(self, schema: Schema) -> None:
        relation: Relation = Relation(schema, ("users", "nope"))

        assert _texts(relation) == _texts(Relation(schema, ("users",)))

    def test_empty_clause_offers_nothing(self, schema: Schema) -> None:
        assert Relation(schema, ()).get_operands() == ()

class TestAmbiguity:
    def test_a_shared_name_loses_its_bare_spelling(self, schema: Schema) -> None:
        """`id` is on both nodes, so SQL refuses the unqualified reference."""

        relation: Relation = Relation(schema, ("users", "posts"))
        names: list[str] = _texts(relation)

        assert "id" not in names
        assert "users.id" in names and "posts.id" in names

    def test_a_unique_name_keeps_it(self, schema: Schema) -> None:
        relation: Relation = Relation(schema, ("users", "posts"))
        names: list[str] = _texts(relation)

        assert "email" in names and "users.email" in names
        assert "title" in names and "posts.title" in names

    def test_ambiguity_is_about_the_clause_not_the_schema(self, schema: Schema) -> None:
        """`title` is on posts and comments, but only posts is in this clause."""

        assert "title" in _texts(Relation(schema, ("users", "posts")))
        assert "title" not in _texts(Relation(schema, ("posts", "comments")))

    def test_a_bare_operand_remembers_its_node(self, schema: Schema) -> None:
        relation: Relation = Relation(schema, ("users", "posts"))

        bare: Operand = [o for o in relation.get_operands() if o.text == "email"][0]
        qualified: Operand = [o for o in relation.get_operands() if o.text == "users.email"][0]

        assert bare.node == "users"
        assert bare.same_column(qualified)

class TestAliases:
    def test_an_aliased_node_answers_to_its_alias(self, schema: Schema) -> None:
        relation: Relation = Relation(schema, ("users u",))
        names: list[str] = _texts(relation)

        assert "u.email" in names
        assert "users.email" not in names

    def test_the_bare_name_survives_an_alias(self, schema: Schema) -> None:
        assert "email" in _texts(Relation(schema, ("users u",)))

    def test_two_aliases_of_one_table_stay_apart(self, schema: Schema) -> None:
        relation: Relation = Relation(schema, ("users u", "users v"))
        names: list[str] = _texts(relation)

        assert "u.email" in names and "v.email" in names
        # Both nodes carry every column, so nothing is unambiguous any more.
        assert "email" not in names

class TestTypes:
    def test_operands_carry_their_field(self, schema: Schema) -> None:
        relation: Relation = Relation(schema, ("users",))

        email: Operand = [o for o in relation.get_operands() if o.text == "email"][0]

        assert email.field.type.name == "VARCHAR"
        assert email.field.is_nullable is False

    def test_filtering_by_class(self, schema: Schema) -> None:
        relation: Relation = Relation(schema, ("users",))

        assert "id" not in _texts(relation, TypeClass.TEXT)
        assert "email" in _texts(relation, TypeClass.TEXT)
        assert _texts(relation, TypeClass.NUMERIC) == ["id", "users.id"]

    def test_an_absent_class_is_empty(self, schema: Schema) -> None:
        assert Relation(schema, ("users",)).get_operands(TypeClass.BINARY) == ()

class TestFilters:
    def test_conditions_are_recorded_in_order(self, schema: Schema) -> None:
        relation: Relation = Relation(schema, ("users",))

        assert relation.use_filter("email = 'a'") is True
        assert relation.use_filter("users.id > 1") is True
        assert relation.get_used_filters() == ("email = 'a'", "users.id > 1")
        assert str(relation) == "email = 'a', users.id > 1"

    def test_an_empty_condition_is_refused(self, schema: Schema) -> None:
        relation: Relation = Relation(schema, ("users",))

        assert relation.use_filter("") is False
        assert relation.get_used_filters() == ()

    def test_copy_shares_the_table_but_not_the_filters(self, schema: Schema) -> None:
        relation: Relation = Relation(schema, ("users",))

        relation.use_filter("email = 'a'")

        clone: Relation = relation.copy()

        clone.use_filter("users.id > 1")

        assert clone.get_used_filters() == ("email = 'a'", "users.id > 1")
        assert relation.get_used_filters() == ("email = 'a'",)
        assert clone.get_operands() == relation.get_operands()
