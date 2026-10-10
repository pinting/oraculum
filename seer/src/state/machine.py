"""A finite state machine as a value.

A machine is its transition table plus the state it stands in. It never
changes: `advance` answers with the machine one step on, or with `None` when the
table has no such edge, so a branch of the syntax graph can hold one and copy
it for nothing.

Standing still is always allowed. The engine may resolve the same boundary
twice while it expands a branch, and taking a keyword a second time must not
read as an illegal move.

What happens *on* a transition is deliberately not here. The machine says
whether a move is legal; the object that owns it decides what entering or
leaving a state means, so the shape of the lifecycle can be read in one table
without the work it triggers getting in the way.
"""

from __future__ import annotations

from enum import Enum
from typing import Generic, Mapping, TypeVar

S = TypeVar("S", bound=Enum)

Transitions = Mapping[S, frozenset[S]]

class Machine(Generic[S]):
    __slots__ = ("_table", "_state")

    def __init__(self, table: "Transitions[S]", initial: S) -> None:
        self._table = table
        self._state = initial

    @property
    def state(self) -> S:
        return self._state

    def is_at(self, *states: S) -> bool:
        return self._state in states

    def can_advance(self, target: S) -> bool:
        return target is self._state or target in self._table.get(self._state, frozenset())

    def advance(self, target: S) -> "Machine[S] | None":
        """The machine standing at `target`, or `None` if that is no legal move."""

        if target is self._state:
            return self

        if not self.can_advance(target):
            return None

        return Machine(self._table, target)

    def __str__(self) -> str:
        return str(self._state.value)

    def __repr__(self) -> str:
        return f"Machine({self._state.name})"

def validate(table: "Transitions[S]", states: type[S]) -> "Transitions[S]":
    """Check a table names every state, so a missing row is a load time error."""

    missing: set[S] = set(states) - set(table)

    if missing:
        raise ValueError(f"transition table has no row for {sorted(s.name for s in missing)}")

    return table
