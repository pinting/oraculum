"""The comparison operators each type class admits, and how its literals are spelled.

`schema.py` has always parsed a column's `Type`, its nullability and its keys;
the condition grammar is what reads them. A condition is offered only when its
sides agree on a class, so the class is what decides which operators a column
may take and what may stand opposite one.

An operator also has a shape, which is how many values stand on its right:

    UNARY    x IS NULL                      nothing
    BINARY   x = y                          one value
    RANGE    x BETWEEN y AND z              two values
    LIST     x IN (y, z, ...)               one literal or more

Values are out of scope. A literal is spelled by the pattern its class names,
and whatever it says inside that pattern is its own business.
"""

from __future__ import annotations

from enum import Enum

from .schema import Field, Type
from .types import TypeClass, classify

class Arity(Enum):
    UNARY = "unary"
    BINARY = "binary"
    RANGE = "range"
    LIST = "list"

class Operator(Enum):
    EQ = "="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    LIKE = "LIKE"
    NOT_LIKE = "NOT LIKE"
    BETWEEN = "BETWEEN"
    NOT_BETWEEN = "NOT BETWEEN"
    IN = "IN"
    NOT_IN = "NOT IN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"

    @property
    def arity(self) -> Arity:
        return ARITIES.get(self, Arity.BINARY)

    @property
    def is_unary(self) -> bool:
        """Whether the operator is the last token of its condition."""

        return self.arity is Arity.UNARY

    def __str__(self) -> str:
        return self.value

EQUALITY: tuple[Operator, ...] = (Operator.EQ, Operator.NE)
ORDERING: tuple[Operator, ...] = (Operator.LT, Operator.LE, Operator.GT, Operator.GE)
MATCHING: tuple[Operator, ...] = (Operator.LIKE, Operator.NOT_LIKE)
RANGING: tuple[Operator, ...] = (Operator.BETWEEN, Operator.NOT_BETWEEN)
MEMBERSHIP: tuple[Operator, ...] = (Operator.IN, Operator.NOT_IN)
NULLITY: tuple[Operator, ...] = (Operator.IS_NULL, Operator.IS_NOT_NULL)

ARITIES: dict[Operator, Arity] = {
    **{operator: Arity.UNARY for operator in NULLITY},
    **{operator: Arity.RANGE for operator in RANGING},
    **{operator: Arity.LIST for operator in MEMBERSHIP},
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

# The classes a value can be written in without naming a column, in the order
# a branch over classes expands in.
LITERAL_CLASSES: tuple[TypeClass, ...] = tuple(LITERALS)

# What a literal is typed as once it stands in a result column.
LITERAL_TYPES: dict[TypeClass, Type] = {
    TypeClass.NUMERIC: Type("NUMERIC"),
    TypeClass.TEXT: Type("TEXT"),
    TypeClass.TEMPORAL: Type("TIMESTAMP"),
    TypeClass.BOOLEAN: Type("BOOLEAN"),
}

# Every class may be compared for equality. Only a class with an order may be
# ranged over, only text may be matched against a pattern, and only a class
# with literals may be tested against a list of them.
BINARY_OPERATORS: dict[TypeClass, tuple[Operator, ...]] = {
    TypeClass.NUMERIC: EQUALITY + ORDERING + RANGING + MEMBERSHIP,
    TypeClass.TEMPORAL: EQUALITY + ORDERING + RANGING + MEMBERSHIP,
    TypeClass.TEXT: EQUALITY + ORDERING + MATCHING + RANGING + MEMBERSHIP,
    TypeClass.BOOLEAN: EQUALITY,
    TypeClass.BINARY: EQUALITY,
    TypeClass.UNKNOWN: EQUALITY,
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

def comparisons(kind: TypeClass) -> tuple[Operator, ...]:
    """The operators that compare a value of `kind` with others, in a stable order."""

    return BINARY_OPERATORS[kind]

def operators_for(field: Field) -> tuple[Operator, ...]:
    """Every operator `field` may stand on the left of, in a stable order."""

    operators: tuple[Operator, ...] = comparisons(classify(field.type))

    if is_nullable(field):
        return operators + NULLITY

    return operators

def is_comparable(left: Type, right: Type) -> bool:
    """Whether the two types may be the sides of one condition."""

    return classify(left) is classify(right)
