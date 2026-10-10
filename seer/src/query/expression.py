"""Expressions: the values a projection writes, as a tree.

An item of the projection is no longer only a column or an aggregate over one;
it is any value SQL computes per row or per group:

    Column      email, u.email
    Literal     1, 'a', TRUE
    Star        the * of COUNT(*)
    Call        LOWER(email), COUNT(DISTINCT email), CAST(id AS TEXT)
    Arithmetic  id + 1
    Predicate   email LIKE 'a%', created_at IS NULL     (only inside CASE)
    Case        CASE WHEN ... THEN ... ELSE ... END
    Window      ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)

The tree is written before the FROM clause exists, so a column is a name and
nothing more: which table supplies it, and so which type it has, is the
resolvers' question until the relation is closed. What a node knows on its
own is

* its **class** where its shape fixes it - `LOWER(...)` is text and `id + 1`
  numeric whatever they are applied to - and otherwise which children its
  class `follows`, so a value can be narrowed after it is written: `MAX(x)` is
  numeric exactly when `x` is, and narrowing it narrows `x` (`narrowing`);
* its **children**, which is what grouping walks: a value is single valued per
  group when it is a grouped key itself, an aggregate, a constant, or built
  only from such values (`grouping.covers`);
* how it is **rendered** with every column replaced by whatever the caller
  says, which is both its text and - with each column replaced by the node it
  resolves to - the key two spellings of one value share.

Once the relation is closed `field` types a node the way the relation types
its columns, which is what a derived table exports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator

from ..model import (
    LITERAL_TYPES,
    Field,
    Function,
    Kinds,
    Operator,
    Type,
    TypeClass,
    column_name,
    is_nullable,
)

Leaf = Callable[["Column"], str]
Resolve = Callable[["Column"], Field]

class Expr:
    """A value, as the projection writes it."""

    __slots__ = ()

    @property
    def kind(self) -> TypeClass | None:
        """The class the shape of the value fixes, or `None` if it `follows` another."""

        return None

    @property
    def is_aggregate(self) -> bool:
        """Whether the value folds a group: an aggregate call outside any window."""

        return False

    def children(self) -> tuple["Expr", ...]:
        return ()

    def follows(self) -> tuple["Expr", ...]:
        """The values whose class this one has, where its own shape does not fix one."""

        return ()

    def render(self, leaf: Leaf) -> str:
        raise NotImplementedError

    def field(self, resolve: Resolve) -> Field:
        """The column the value is, once `resolve` types its columns."""

        raise NotImplementedError

    def walk(self) -> Iterator["Expr"]:
        """This value and every value inside it, outermost first."""

        yield self

        for child in self.children():
            yield from child.walk()

    def columns(self) -> Iterator["Column"]:
        """Every column the value names, inside aggregates and windows too."""

        for node in self.walk():
            if isinstance(node, Column):
                yield node

    def aggregates(self) -> bool:
        """Whether an aggregate is written anywhere in the value."""

        return any(node.is_aggregate for node in self.walk())

    def windows(self) -> bool:
        return any(isinstance(node, Window) for node in self.walk())

    def __str__(self) -> str:
        return self.render(lambda column: column.text)

@dataclass(frozen=True)
class Column(Expr):
    qualifier: str
    """The alias the column was written under; `""` for a bare column."""

    name: str

    @property
    def text(self) -> str:
        return column_name(self.qualifier, self.name)

    def render(self, leaf: Leaf) -> str:
        return leaf(self)

    def field(self, resolve: Resolve) -> Field:
        return resolve(self)

@dataclass(frozen=True)
class Literal(Expr):
    text: str
    of: TypeClass

    @property
    def kind(self) -> TypeClass:
        return self.of

    def render(self, leaf: Leaf) -> str:
        return self.text

    def field(self, resolve: Resolve) -> Field:
        return Field(name=self.text, type=LITERAL_TYPES[self.of], is_nullable=False)

@dataclass(frozen=True)
class Star(Expr):
    """The `*` of `COUNT(*)`, which is no value of its own."""

    def render(self, leaf: Leaf) -> str:
        return "*"

STAR: Star = Star()

@dataclass(frozen=True)
class Call(Expr):
    function: Function
    arguments: tuple[Expr, ...]
    distinct: bool = False

    @property
    def kind(self) -> TypeClass | None:
        return self.function.kind

    @property
    def is_aggregate(self) -> bool:
        return self.function.is_aggregate

    def children(self) -> tuple[Expr, ...]:
        return self.arguments

    def follows(self) -> tuple[Expr, ...]:
        if self.function.kind is not None or not self.arguments:
            return ()

        return self.arguments if self.function.uniform else self.arguments[:1]

    def render(self, leaf: Leaf) -> str:
        return self.function.spell([argument.render(leaf) for argument in self.arguments], self.distinct)

    def field(self, resolve: Resolve) -> Field:
        arguments: list[Field | None] = [
            None if isinstance(argument, Star) else argument.field(resolve)
            for argument in self.arguments
        ]

        return self.function.apply(arguments, str(self))

@dataclass(frozen=True)
class Arithmetic(Expr):
    left: Expr
    operator: str
    right: Expr

    @property
    def kind(self) -> TypeClass:
        return TypeClass.NUMERIC

    def children(self) -> tuple[Expr, ...]:
        return (self.left, self.right)

    def render(self, leaf: Leaf) -> str:
        return f"{self.left.render(leaf)} {self.operator} {self.right.render(leaf)}"

    def field(self, resolve: Resolve) -> Field:
        nullable: bool = any(is_nullable(side.field(resolve)) for side in self.children())

        return Field(name=str(self), type=Type("NUMERIC"), is_nullable=nullable)

@dataclass(frozen=True)
class Predicate(Expr):
    """A condition a `CASE` branches on: `left <operator> [right]`."""

    left: Expr
    operator: Operator
    right: Expr | None = None

    @property
    def kind(self) -> TypeClass:
        return TypeClass.BOOLEAN

    def children(self) -> tuple[Expr, ...]:
        return (self.left,) if self.right is None else (self.left, self.right)

    def render(self, leaf: Leaf) -> str:
        if self.right is None:
            return f"{self.left.render(leaf)} {self.operator}"

        return f"{self.left.render(leaf)} {self.operator} {self.right.render(leaf)}"

    def field(self, resolve: Resolve) -> Field:
        return Field(name=str(self), type=Type("BOOLEAN"))

@dataclass(frozen=True)
class Case(Expr):
    of: TypeClass
    """The class every branch's value has, fixed when `CASE` was written."""

    branches: tuple[tuple[Predicate, Expr], ...]
    otherwise: Expr | None = None

    @property
    def kind(self) -> TypeClass:
        return self.of

    def values(self) -> tuple[Expr, ...]:
        values: tuple[Expr, ...] = tuple(value for _, value in self.branches)

        return values if self.otherwise is None else values + (self.otherwise,)

    def children(self) -> tuple[Expr, ...]:
        conditions: tuple[Expr, ...] = tuple(condition for condition, _ in self.branches)

        return conditions + self.values()

    def render(self, leaf: Leaf) -> str:
        text: str = "CASE"

        for condition, value in self.branches:
            text += f" WHEN {condition.render(leaf)} THEN {value.render(leaf)}"

        if self.otherwise is not None:
            text += f" ELSE {self.otherwise.render(leaf)}"

        return f"{text} END"

    def field(self, resolve: Resolve) -> Field:
        fields: list[Field] = [value.field(resolve) for value in self.values()]

        # Without an ELSE a row no branch matches is NULL.
        nullable: bool = self.otherwise is None or any(is_nullable(field) for field in fields)

        return Field(name=str(self), type=fields[0].type, is_nullable=nullable)

# How a key of a window, or of an ORDER BY, is ordered: `""`, `"ASC"` or `"DESC"`.
Direction = str

@dataclass(frozen=True)
class Window(Expr):
    """`<call> OVER (PARTITION BY ... ORDER BY ...)`.

    A windowed aggregate folds no group - it is evaluated per row, over the
    rows of its window - so the window is no aggregate, and its arguments and
    keys are values of the row like any other.
    """

    call: Call
    partition: tuple[Expr, ...] = ()
    order: tuple[tuple[Expr, Direction], ...] = ()

    @property
    def kind(self) -> TypeClass | None:
        return self.call.kind

    def children(self) -> tuple[Expr, ...]:
        return self.call.arguments + self.partition + tuple(key for key, _ in self.order)

    def follows(self) -> tuple[Expr, ...]:
        return self.call.follows()

    def render(self, leaf: Leaf) -> str:
        clauses: list[str] = []

        if self.partition:
            clauses.append("PARTITION BY " + ", ".join(key.render(leaf) for key in self.partition))

        if self.order:
            clauses.append("ORDER BY " + ", ".join(
                f"{key.render(leaf)} {direction}".rstrip() for key, direction in self.order
            ))

        return f"{self.call.render(leaf)} OVER ({' '.join(clauses)})"

    def field(self, resolve: Resolve) -> Field:
        return self.call.field(resolve)

def narrowing(expr: Expr, kinds: Kinds) -> tuple[Column, ...] | None:
    """The columns that have to be of `kinds` for `expr` to be; `None` if it cannot be.

    A value whose shape fixes its class either is of `kinds` already or never
    will be. One that follows its children is of `kinds` exactly when they are,
    down to the columns, which are the only thing still undecided.
    """

    if expr.kind is not None:
        return () if expr.kind in kinds else None

    if isinstance(expr, Column):
        return (expr,)

    columns: list[Column] = []

    for child in expr.follows():
        narrowed: tuple[Column, ...] | None = narrowing(child, kinds)

        if narrowed is None:
            return None

        columns.extend(narrowed)

    return tuple(columns)
