"""The SOURCE part of a query: the FROM clause while it is being written.

The selection knows which nodes the projection requires and which it rules
out; `Relationships` knows which nodes the foreign keys connect. Placing an
entry or a join has to agree with both, and with one more rule neither of them
can see: a column the projection names bare may be supplied by one placed node
at most. The algebra already guarantees that between two different tables, but
two nodes of the *same* table - `users` and `users AS u` - are one variable to
it, and SQL would still refuse the bare name between them. And a node may only
be placed where the aliases still to come can be placed after it
(`placement.py`).

Everything that might be offered is filtered by the same test that placing it
applies, so the grammar never offers a node it would then have to refuse.

A recursive member adds two rules of its own: the definition it reads may be
placed once at most, and only by inner joins - an outer join could pad the
recursion with rows it never produced, and both SQLite and PostgreSQL refuse
one there.

The part is bound to the selection it was opened over, because placing a node
discharges what the selection demanded; the selection stays the owner.
"""

from __future__ import annotations

from typing import Iterable

from ..model import Schema, unqualify
from ..resolution import JOIN_TYPES, Conflicts, JoinType, Neighbor, Relationships
from .placement import placeable
from .selection import Selection

class Sources:
    __slots__ = ("_schema", "_selection", "_relationships", "_join_types")

    def __init__(
        self,
        schema: Schema | None = None,
        selection: Selection | None = None,
        join_types: tuple[JoinType, ...] = tuple(JOIN_TYPES),
    ) -> None:
        if schema is None or selection is None:
            return

        self._schema = schema
        self._selection = selection
        self._relationships = Relationships(schema, selection.conflicts.get_required_tables())
        self._join_types: tuple[JoinType, ...] = join_types

    def copy(self, selection: Selection) -> "Sources":
        """A copy bound to `selection`, the copy of the one this was bound to."""

        clone: Sources = Sources.__new__(Sources)

        clone._schema = self._schema
        clone._selection = selection
        clone._relationships = self._relationships.copy()
        clone._join_types = self._join_types

        return clone

    @property
    def _conflicts(self) -> Conflicts:
        return self._selection.conflicts

    def nodes(self) -> tuple[str, ...]:
        """The nodes placed so far, in the order they were placed."""

        return self._relationships.get_used_nodes()

    def nullable(self) -> frozenset[str]:
        """The placed nodes an outer join may pad with NULLs."""

        return self._relationships.get_nullable_nodes()

    def is_satisfied(self) -> bool:
        """Whether everything the projection demanded has been placed."""

        return self._conflicts.is_satisfied()

    def places(self, table: str) -> bool:
        """Whether a node of `table` has been placed, under any alias."""

        return any(unqualify(node)[0] == table for node in self.nodes())

    def _admits(self, node: str) -> bool:
        """Whether placing `node` keeps every rule the clause has.

        Every bare column keeps one supplier, a table that may be placed once
        is not placed twice, and the aliases still to come stay placeable.
        """

        # Placing it has to leave the aliases still to come placeable too, or
        # the clause would be stuck waiting for a node it could never place.
        trial: Conflicts = self._conflicts.copy()

        if node in self._conflicts.get_required_tables() and not trial.use_table(node):
            return False

        return placeable(
            self._schema,
            trial,
            self._selection.bare_columns(),
            self.nodes() + (node,),
            self._selection.once,
        )

    def entries(self) -> list[str]:
        """The nodes a new FROM entry may open with.

        The required ones - and, where the projection requires nothing at all,
        as `COUNT(*)` alone does, any table the first entry likes.
        """

        candidates: Iterable[str] = self._conflicts.get_required_tables()

        if not self.nodes() and self._conflicts.is_satisfied():
            candidates = set(self._schema.tables) - self._conflicts.get_excluded_tables()

        return sorted(node for node in candidates if self._admits(node))

    def place(self, node: str) -> bool:
        """Open a FROM entry at `node` and satisfy it."""

        if node not in self.entries() or not self._conflicts.use_table(node):
            return False

        return self._relationships.use_table(node)

    def neighbors(self) -> tuple[Neighbor, ...]:
        """Nodes the current entry may be joined to."""

        return tuple(
            neighbor
            for neighbor in self._relationships.get_joinable_neighbors(
                self._conflicts.get_excluded_tables()
            )
            if self._admits(neighbor.table)
        )

    def join_types(self) -> tuple[JoinType, ...]:
        """The kinds of join the clause may write."""

        return self._join_types

    def join(self, neighbor: Neighbor, join_type: JoinType) -> bool:
        """Join `neighbor` into the current entry, satisfying it if required."""

        if neighbor not in self.neighbors() or join_type not in self._join_types:
            return False

        if neighbor.table in self._conflicts.get_required_tables():
            self._conflicts.use_table(neighbor.table)

        return self._relationships.join_table(neighbor, join_type)

    def __str__(self) -> str:
        return str(self._relationships)
