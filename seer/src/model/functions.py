"""Aggregate functions: what each accepts, and the column it produces.

An aggregate is a typed map from a column to a column. What it accepts is a set
of type classes, because summing text or averaging a timestamp is not a
statement about anything; what it produces is a `Field`, so the result can be
compared in a HAVING condition and exported as the column of a derived table
exactly like a column the schema declared.

    COUNT(*) | COUNT(<any>)    BIGINT, never NULL
    SUM(<numeric>)             the argument's type
    AVG(<numeric>)             DECIMAL
    MIN(<ordered>)             the argument's type
    MAX(<ordered>)             the argument's type

Every result but `COUNT` may be NULL: they are NULL over an empty group.
"""

from __future__ import annotations

from dataclasses import dataclass

from .schema import Field, Type
from .types import TypeClass, classify

# The classes with an order, which is what MIN and MAX need.
ORDERED: frozenset[TypeClass] = frozenset({
    TypeClass.NUMERIC,
    TypeClass.TEXT,
    TypeClass.TEMPORAL,
})

NUMERIC: frozenset[TypeClass] = frozenset({TypeClass.NUMERIC})

@dataclass(frozen=True)
class Function:
    name: str
    """How it is spelled, upper case like every keyword."""

    accepts: frozenset[TypeClass] | None
    """The classes an argument may have; `None` for every class."""

    star: bool = False
    """Whether `*` may stand for the argument."""

    returns: Type | None = None
    """The result type; `None` for the argument's own."""

    nullable: bool = True

    def admits(self, field: Field) -> bool:
        return self.accepts is None or classify(field.type) in self.accepts

    def apply(self, argument: Field | None, name: str) -> Field:
        """The column `FN(argument)` produces, called `name`."""

        if self.returns is not None:
            type: Type = self.returns
        else:
            assert argument is not None, f"{self.name} has no type without an argument"

            type = argument.type

        return Field(name=name, type=type, is_nullable=self.nullable)

    def spell(self, argument: str | None) -> str:
        """`COUNT(*)`, `SUM(posts.id)`."""

        return f"{self.name}({'*' if argument is None else argument})"

    def __str__(self) -> str:
        return self.name

COUNT: Function = Function("COUNT", None, star=True, returns=Type("BIGINT"), nullable=False)
SUM: Function = Function("SUM", NUMERIC)
AVG: Function = Function("AVG", NUMERIC, returns=Type("DECIMAL"))
MIN: Function = Function("MIN", ORDERED)
MAX: Function = Function("MAX", ORDERED)

# In the order the grammar offers them, which is the order they expand in.
FUNCTIONS: tuple[Function, ...] = (AVG, COUNT, MAX, MIN, SUM)

# Every distinct argument restriction, which is what the resolvers precompute
# their typed constraints for.
ARGUMENT_KINDS: tuple[frozenset[TypeClass], ...] = tuple(
    dict.fromkeys(f.accepts for f in FUNCTIONS if f.accepts is not None)
)

def function_names() -> frozenset[str]:
    return frozenset(f.name for f in FUNCTIONS)
