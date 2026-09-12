"""`operators.py` - type classes, and what each admits.

`Field.type` and `Field.is_nullable` were parsed from the very first schema and
read by nothing until the WHERE clause arrived. These cover the classification
itself and the two gates built over it: which operators a column may take, and
which columns may face each other across one.
"""

from __future__ import annotations

import pytest

from src.operators import (
    BINARY_OPERATORS,
    CLASSES,
    EQUALITY,
    LITERALS,
    MATCHING,
    NULLITY,
    ORDERING,
    Operator,
    TypeClass,
    classify,
    is_comparable,
    is_nullable,
    literal_for,
    operators_for,
)
from src.schema import Field, Type

def _field(
    name: str,
    type_name: str,
    nullable: bool = True,
    primary_key: bool = False,
) -> Field:
    return Field(
        name=name,
        type=Type(name=type_name),
        is_nullable=nullable,
        is_primary_key=primary_key,
    )

class TestClassify:
    @pytest.mark.parametrize(
        "name,kind",
        [
            ("BIGINT", TypeClass.NUMERIC),
            ("INT", TypeClass.NUMERIC),
            ("DECIMAL", TypeClass.NUMERIC),
            ("VARCHAR", TypeClass.TEXT),
            ("TEXT", TypeClass.TEXT),
            ("TIMESTAMP", TypeClass.TEMPORAL),
            ("DATE", TypeClass.TEMPORAL),
            ("BOOLEAN", TypeClass.BOOLEAN),
            ("BYTEA", TypeClass.BINARY),
        ],
    )
    def test_known_names(self, name: str, kind: TypeClass) -> None:
        assert classify(Type(name=name)) is kind

    def test_length_is_ignored(self) -> None:
        assert classify(Type(name="VARCHAR", length=255)) is TypeClass.TEXT

    def test_unparsed_type_is_unknown(self) -> None:
        """`schema._parse_type` names a column it could not read `UNKNOWN`."""

        assert classify(Type(name="UNKNOWN")) is TypeClass.UNKNOWN
        assert classify(Type(name="GEOGRAPHY")) is TypeClass.UNKNOWN

    def test_every_class_but_unknown_has_a_spelling(self) -> None:
        """A class no type name reaches could never be produced by a schema."""

        assert set(CLASSES.values()) == set(TypeClass) - {TypeClass.UNKNOWN}

class TestOperatorsFor:
    def test_numeric_is_ordered_but_not_matched(self) -> None:
        offered = operators_for(_field("id", "BIGINT", nullable=False))

        assert set(offered) == set(EQUALITY + ORDERING)
        assert Operator.LIKE not in offered

    def test_text_may_be_matched(self) -> None:
        offered = operators_for(_field("email", "VARCHAR", nullable=False))

        assert set(offered) == set(EQUALITY + ORDERING + MATCHING)

    def test_boolean_is_equality_only(self) -> None:
        offered = operators_for(_field("verified", "BOOLEAN", nullable=False))

        assert set(offered) == set(EQUALITY)

    def test_unknown_is_equality_only(self) -> None:
        offered = operators_for(_field("shape", "GEOGRAPHY", nullable=False))

        assert set(offered) == set(EQUALITY)

    def test_nullable_column_gains_the_null_tests(self) -> None:
        offered = operators_for(_field("created_at", "TIMESTAMP"))

        assert Operator.IS_NULL in offered
        assert Operator.IS_NOT_NULL in offered

    def test_not_null_column_has_no_null_tests(self) -> None:
        offered = operators_for(_field("email", "VARCHAR", nullable=False))

        assert Operator.IS_NULL not in offered

    def test_primary_key_has_no_null_tests(self) -> None:
        """`id BIGINT PRIMARY KEY` leaves `is_nullable` at its default."""

        key: Field = _field("id", "BIGINT", nullable=True, primary_key=True)

        assert is_nullable(key) is False
        assert Operator.IS_NULL not in operators_for(key)

    def test_order_is_stable(self) -> None:
        field: Field = _field("email", "VARCHAR")

        assert operators_for(field) == operators_for(field)
        assert operators_for(field)[-len(NULLITY):] == NULLITY

class TestOperator:
    def test_only_the_null_tests_are_unary(self) -> None:
        unary = {operator for operator in Operator if operator.is_unary}

        assert unary == set(NULLITY)

    def test_text_is_what_is_emitted(self) -> None:
        assert str(Operator.NOT_LIKE) == "NOT LIKE"
        assert str(Operator.IS_NOT_NULL) == "IS NOT NULL"
        assert str(Operator.NE) == "!="

class TestComparability:
    def test_same_class_compares(self) -> None:
        assert is_comparable(Type(name="VARCHAR", length=255), Type(name="TEXT"))
        assert is_comparable(Type(name="INT"), Type(name="BIGINT"))

    def test_different_classes_do_not(self) -> None:
        assert not is_comparable(Type(name="BIGINT"), Type(name="VARCHAR"))
        assert not is_comparable(Type(name="TIMESTAMP"), Type(name="BIGINT"))

    def test_unknown_only_matches_unknown(self) -> None:
        """A type nobody recognised is not quietly comparable to everything."""

        assert is_comparable(Type(name="GEOGRAPHY"), Type(name="GEOMETRY"))
        assert not is_comparable(Type(name="GEOGRAPHY"), Type(name="TEXT"))

class TestLiterals:
    @pytest.mark.parametrize(
        "kind",
        [TypeClass.NUMERIC, TypeClass.TEXT, TypeClass.TEMPORAL, TypeClass.BOOLEAN],
    )
    def test_spellable_classes_have_a_pattern(self, kind: TypeClass) -> None:
        assert literal_for(kind) == LITERALS[kind]

    @pytest.mark.parametrize("kind", [TypeClass.BINARY, TypeClass.UNKNOWN])
    def test_opaque_classes_take_columns_only(self, kind: TypeClass) -> None:
        assert literal_for(kind) is None

    def test_every_class_has_operators(self) -> None:
        assert set(BINARY_OPERATORS) == set(TypeClass)
