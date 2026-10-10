"""The comparison operators each type class admits, and how its literals are spelled.

`schema.py` has always parsed a column's `Type`, its nullability and its keys;
the condition grammar is what reads them. A condition is offered only when its
two sides agree on a class, so the class is what decides which operators a
column may take and what may stand opposite one.

Values are out of scope. A literal is spelled by the pattern its class names,
and whatever it says inside that pattern is its own business.
"""

from __future__ import annotations

from enum import Enum

from .schema import Field, Type
from .types import TypeClass, classify

class Operator(Enum):
    EQ = "="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    LIKE = "LIKE"
    NOT_LIKE = "NOT LIKE"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"

    @property
    def is_unary(self) -> bool:
        """Whether the operator is the last token of its condition."""

        return self in NULLITY

    def __str__(self) -> str:
        return self.value

EQUALITY: tuple[Operator, ...] = (Operator.EQ, Operator.NE)
ORDERING: tuple[Operator, ...] = (Operator.LT, Operator.LE, Operator.GT, Operator.GE)
MATCHING: tuple[Operator, ...] = (Operator.LIKE, Operator.NOT_LIKE)
NULLITY: tuple[Operator, ...] = (Operator.IS_NULL, Operator.IS_NOT_NULL)

# Every class may be compared for equality. Only a class with an order may be
# ranged over, and only text may be matched against a pattern.
BINARY_OPERATORS: dict[TypeClass, tuple[Operator, ...]] = {
    TypeClass.NUMERIC: EQUALITY + ORDERING,
    TypeClass.TEMPORAL: EQUALITY + ORDERING,
    TypeClass.TEXT: EQUALITY + ORDERING + MATCHING,
    TypeClass.BOOLEAN: EQUALITY,
    TypeClass.BINARY: EQUALITY,
    TypeClass.UNKNOWN: EQUALITY,
}

# How a literal of each class is spelled. The pattern fixes the shape and says
# nothing about the value, which is the whole of what "typed" means here. A
# class with no entry takes column operands only.
LITERALS: dict[TypeClass, str] = {
    TypeClass.NUMERIC: r"-?[0-9]+(\.[0-9]+)?",
    TypeClass.TEXT: r"'[^']*'",
    TypeClass.TEMPORAL: r"'[0-9]{4}-[0-9]{2}-[0-9]{2}( [0-9]{2}:[0-9]{2}:[0-9]{2})?'",
    TypeClass.BOOLEAN: r"TRUE|FALSE",
}

def literal_for(kind: TypeClass) -> str | None:
    """The pattern a literal of `kind` is written by, if it has one."""

    return LITERALS.get(kind)

def is_nullable(field: Field) -> bool:
    """Whether the column can actually hold NULL.

    A primary key cannot, whether or not it was written `NOT NULL` - and it
    usually is not, so the parser leaves `is_nullable` at its `True` default
    there and this is the only thing that catches it.
    """

    return field.is_nullable and not field.is_primary_key

def operators_for(field: Field) -> tuple[Operator, ...]:
    """Every operator `field` may stand on the left of, in a stable order."""

    operators: tuple[Operator, ...] = BINARY_OPERATORS[classify(field.type)]

    if is_nullable(field):
        return operators + NULLITY

    return operators

def is_comparable(left: Type, right: Type) -> bool:
    """Whether the two types may be the sides of one condition."""

    return classify(left) is classify(right)
