"""Compound queries: members joined by set operators.

    <select> UNION [ALL] <select> | <select> INTERSECT <select> | <select> EXCEPT <select>

Each member is a query of its own - its own projection, FROM clause and
grouping - and they are siblings, not a stack: none of them reads another.
What ties them is their result. Every member after the first has to produce
the first one's shape (`shape.py`), and the compound's result is theirs merged
(`derivation.merge`), which is what an ORDER BY after the last member and the
table a definition exports both read.

The member being written holds the compound of the ones before it, so a
compound is only ever made of closed members and is a value like they are.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from .derivation import Result, merge

if TYPE_CHECKING:
    from .virtual import VirtualTable

class SetOperator(Enum):
    UNION = "UNION"
    UNION_ALL = "UNION ALL"
    INTERSECT = "INTERSECT"
    EXCEPT = "EXCEPT"

    @property
    def is_union(self) -> bool:
        """Whether it may join a recursive member to the members before it."""

        return self in (SetOperator.UNION, SetOperator.UNION_ALL)

    def __str__(self) -> str:
        return self.value

SET_OPERATORS: tuple[SetOperator, ...] = tuple(SetOperator)

@dataclass(frozen=True)
class Compound:
    members: tuple["VirtualTable", ...]
    operators: tuple[SetOperator, ...]

    @property
    def first(self) -> "VirtualTable":
        return self.members[0]

    def joined(self, member: "VirtualTable", operator: SetOperator) -> "Compound":
        """This compound with the closed `member` and the operator after it."""

        return Compound(self.members + (member,), self.operators + (operator,))

    @classmethod
    def starting(cls, member: "VirtualTable", operator: SetOperator) -> "Compound":
        return cls((member,), (operator,))

    @property
    def operator(self) -> SetOperator:
        """The operator the member being written follows."""

        return self.operators[-1]

    def result(self) -> Result:
        return merge([member.own_result() for member in self.members])

    def __str__(self) -> str:
        return " ".join(f"({member.name or 'main'}) {operator}" for member, operator in zip(self.members, self.operators))
