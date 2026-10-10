"""Functions: what each accepts, what it produces, and where it may stand.

A function is a typed map from values to a value. What it accepts is a set of
type classes per argument, because summing text or lower casing a timestamp is
not a statement about anything; what it produces is a `Field`, so the result
can be compared, grouped on and exported as the column of a derived table
exactly like a column the schema declared.

Every function has a role, which is what decides where it may be written:

* an **aggregate** folds the rows of a group into one value. It may not be
  nested in another aggregate, and it makes the query an aggregated one;
* a **scalar** function maps the values of one row to one, and may stand
  anywhere a value may;
* a **ranking** function numbers the rows of a window, and means nothing
  outside one - it is only ever written with `OVER`.

    AVG([DISTINCT] <numeric>)          DECIMAL
    COUNT(*) | COUNT([DISTINCT] <any>) BIGINT, never NULL
    MAX(<ordered>), MIN(<ordered>)     the argument's type
    SUM([DISTINCT] <numeric>)          the argument's type

    ABS(<numeric>), ROUND(<numeric>)   the argument's type
    CAST(<any> AS TEXT)                TEXT
    COALESCE(<x>, <x>)                 the first argument's type, of one class
    LENGTH(<text>)                     BIGINT
    LOWER, UPPER, TRIM(<text>)         TEXT

    ROW_NUMBER() | RANK() | DENSE_RANK()   BIGINT, never NULL

Every one of them exists, spelled the same way, in SQLite and PostgreSQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .operators import is_nullable
from .schema import Field, Type
from .types import Kinds, TypeClass, classify

class Role(Enum):
    AGGREGATE = "aggregate"
    SCALAR = "scalar"
    RANKING = "ranking"

class Nulls(Enum):
    """When the result may be NULL."""

    NEVER = "never"
    EMPTY = "empty"
    """An aggregate: NULL over a group with nothing to fold."""

    ANY = "any"
    """NULL where any argument is."""

    ALL = "all"
    """NULL only where every argument is - `COALESCE`."""

# The classes with an order, which is what MIN and MAX need.
ORDERED: Kinds = frozenset({TypeClass.NUMERIC, TypeClass.TEXT, TypeClass.TEMPORAL})

NUMERIC: Kinds = frozenset({TypeClass.NUMERIC})
TEXT: Kinds = frozenset({TypeClass.TEXT})

@dataclass(frozen=True)
class Function:
    name: str
    """How it is spelled, upper case like every keyword."""

    role: Role

    parameters: tuple[Kinds | None, ...] = ()
    """The classes each argument may have; `None` for every class."""

    returns: Type | None = None
    """The result type; `None` for the first argument's own."""

    nulls: Nulls = Nulls.ANY

    star: bool = False
    """Whether `*` may stand for the argument: `COUNT(*)`."""

    distinct: bool = False
    """Whether the argument may be preceded by `DISTINCT`."""

    uniform: bool = False
    """Whether every argument has to be of one class, which is the result's."""

    ordered: bool = False
    """Whether its window has to be ordered, which ranking is meaningless without."""

    target: str | None = None
    """The type a cast spells after its `AS`, which makes it a cast."""

    @property
    def kind(self) -> TypeClass | None:
        """The class of the result, or `None` where it is the argument's."""

        return None if self.returns is None else classify(self.returns)

    @property
    def is_aggregate(self) -> bool:
        return self.role is Role.AGGREGATE

    def accepts(self, position: int = 0) -> Kinds | None:
        return self.parameters[position]

    def admits(self, field: Field, position: int = 0) -> bool:
        accepted: Kinds | None = self.accepts(position)

        return accepted is None or classify(field.type) in accepted

    def apply(self, arguments: Sequence[Field | None], name: str) -> Field:
        """The column `FN(arguments)` produces, called `name`.

        `None` stands for the `*` of `COUNT(*)`, which has no column.
        """

        if self.returns is not None:
            type: Type = self.returns
        else:
            first: Field | None = arguments[0] if arguments else None

            assert first is not None, f"{self.name} has no type without an argument"

            type = first.type

        columns: list[Field] = [argument for argument in arguments if argument is not None]

        if self.nulls is Nulls.NEVER:
            nullable: bool = False
        elif self.nulls is Nulls.EMPTY:
            nullable = True
        elif self.nulls is Nulls.ANY:
            nullable = any(is_nullable(column) for column in columns)
        else:
            nullable = bool(columns) and all(is_nullable(column) for column in columns)

        return Field(name=name, type=type, is_nullable=nullable)

    def spell(self, arguments: Sequence[str], distinct: bool = False) -> str:
        """`COUNT(*)`, `SUM(DISTINCT posts.id)`, `CAST(id AS TEXT)`, `RANK()`."""

        inner: str = ", ".join(arguments)

        if self.target is not None:
            return f"{self.name}({inner} AS {self.target})"

        if distinct:
            inner = f"DISTINCT {inner}"

        return f"{self.name}({inner})"

    def __str__(self) -> str:
        return self.name

def _aggregate(name: str, accepts: Kinds | None, **options) -> Function:
    return Function(name, Role.AGGREGATE, (accepts,), nulls=Nulls.EMPTY, **options)

def _scalar(name: str, *parameters: Kinds | None, **options) -> Function:
    return Function(name, Role.SCALAR, parameters, **options)

def _ranking(name: str, **options) -> Function:
    return Function(name, Role.RANKING, (), returns=Type("BIGINT"), nulls=Nulls.NEVER, **options)

AVG: Function = _aggregate("AVG", NUMERIC, returns=Type("DECIMAL"), distinct=True)
COUNT: Function = Function(
    "COUNT", Role.AGGREGATE, (None,), returns=Type("BIGINT"), nulls=Nulls.NEVER, star=True, distinct=True,
)
MAX: Function = _aggregate("MAX", ORDERED)
MIN: Function = _aggregate("MIN", ORDERED)
SUM: Function = _aggregate("SUM", NUMERIC, distinct=True)

ABS: Function = _scalar("ABS", NUMERIC)
CAST: Function = _scalar("CAST", None, returns=Type("TEXT"), target="TEXT")
COALESCE: Function = _scalar("COALESCE", None, None, uniform=True, nulls=Nulls.ALL)
LENGTH: Function = _scalar("LENGTH", TEXT, returns=Type("BIGINT"))
LOWER: Function = _scalar("LOWER", TEXT, returns=Type("TEXT"))
ROUND: Function = _scalar("ROUND", NUMERIC)
TRIM: Function = _scalar("TRIM", TEXT, returns=Type("TEXT"))
UPPER: Function = _scalar("UPPER", TEXT, returns=Type("TEXT"))

DENSE_RANK: Function = _ranking("DENSE_RANK", ordered=True)
RANK: Function = _ranking("RANK", ordered=True)
ROW_NUMBER: Function = _ranking("ROW_NUMBER")

# In the order the grammar offers them, which is the order they expand in.
AGGREGATES: tuple[Function, ...] = (AVG, COUNT, MAX, MIN, SUM)
SCALARS: tuple[Function, ...] = (ABS, CAST, COALESCE, LENGTH, LOWER, ROUND, TRIM, UPPER)
RANKINGS: tuple[Function, ...] = (DENSE_RANK, RANK, ROW_NUMBER)

FUNCTIONS: tuple[Function, ...] = AGGREGATES + SCALARS + RANKINGS

# The classes a value folding a group into one can have: what an aggregate
# produces, or every class it accepts where it keeps its argument's. A scalar
# over an aggregate adds none, so nothing of another class - a boolean, a
# binary value - can ever be one row of a whole query.
AGGREGATED: Kinds = frozenset().union(*(
    frozenset({function.kind}) if function.kind is not None else (function.accepts(0) or frozenset())
    for function in AGGREGATES
))

def function_names() -> frozenset[str]:
    return frozenset(f.name for f in FUNCTIONS)
