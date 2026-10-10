"""Operands: the values of a closed relation, and the keys they share.

An operand is a column of a node of the FROM clause, together with how it is
written and the `Field` it is, or a function applied to operands, which is an
operand too - what a condition compares, what a GROUP BY keys on and what an
ORDER BY sorts by. Every one has a **key**, the value it is regardless of
spelling: a column is keyed by its node, so `email` and `users.email` share one
where `users` supplies it; a call by its function and its arguments' keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..model import Field, Function, TypeClass, classify

def column_key(node: str, name: str) -> str:
    """The identity of a column of the clause, however it is spelled."""

    return f"{node}.{name}"

@dataclass(frozen=True)
class Operand:
    """One value of the virtual table, and how a condition names it.

    Usually a column of a node. A function applied to operands is an operand
    too, of the type the function produces - which is what a HAVING condition
    compares, what GROUP BY may key on and what ORDER BY may sort by.
    """

    node: str
    """The FROM node it came from, `"users"` or `"users u"`; `""` for a computed value."""

    name: str
    """The column name, unqualified; the text itself for a computed value."""

    text: str
    """How it is written: `"email"` bare, `"u.email"` qualified, `"LOWER(email)"`."""

    field: Field
    """The column, or the column the value would be, which carries the type."""

    key: str
    """What two spellings of one value share: `email` and `u.email` where `u`
    is the only node supplying it, `LOWER(email)` and `LOWER(u.email)` too."""

    @classmethod
    def column(cls, node: str, name: str, text: str, field: Field) -> "Operand":
        return cls(node, name, text, field, column_key(node, name))

    def same_value(self, other: "Operand") -> bool:
        """Whether both name the same value, however each is spelled."""

        return self.key == other.key

    @property
    def kind(self) -> TypeClass:
        return classify(self.field.type)

    @property
    def is_column(self) -> bool:
        return bool(self.node)

    @staticmethod
    def call(function: Function, arguments: Sequence["Operand"], distinct: bool = False) -> "Operand":
        """`FN(arguments)`, a value of the type `function` produces.

        It belongs to no node, so it is the same value as another only where
        the function and the arguments are.
        """

        text: str = function.spell([argument.text for argument in arguments], distinct)
        key: str = function.spell([argument.key for argument in arguments], distinct)

        return Operand("", text, text, function.apply([a.field for a in arguments], text), key)

    @staticmethod
    def star(function: Function) -> "Operand":
        """`FN(*)`, for the function that takes one."""

        text: str = function.spell(["*"])

        return Operand("", text, text, function.apply([None], text), text)

    def __str__(self) -> str:
        return self.text
