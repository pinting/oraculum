"""The SOURCE part of a query: the FROM clause while it is being written.

The selection knows which nodes the projection requires and which it rules
out; `Relationships` knows which nodes the foreign keys connect. Placing an
entry or a join has to agree with both, and with one more rule neither of them
can see: a column the projection names bare may be supplied by one placed node
at most. The algebra already guarantees that between two different tables, but
two nodes of the *same* table - `users` and `users AS u` - are one variable to
it, and SQL would still refuse the bare name between them.

Everything that might be offered is filtered by the same test that placing it
applies, so the grammar never offers a node it would then have to refuse.

The part is bound to the selection it was opened over, because placing a node
discharges what the selection demanded; the selection stays the owner.
"""

from __future__ import annotations

from typing import Iterable

from ..model import Schema, unqualify
from ..resolution import Conflicts, JoinType, Neighbor, Relationships
from .selection import Selection

class Sources:
    __slots__ = ("_schema", "_selection", "_relationships")

    def __init__(self, schema: Schema | None = None, selection: Selection | None = None) -> None:
        if schema is None or selection is None:
            return

        self._schema = schema
        self._selection = selection
        self._relationships = Relationships(schema, selection.conflicts.get_required_tables())

    def copy(self, selection: Selection) -> "Sources":
        """A copy bound to `selection`, the copy of the one this was bound to."""

        clone: Sources = Sources.__new__(Sources)

        clone._schema = self._schema
        clone._selection = selection
        clone._relationships = self._relationships.copy()

        return clone

    @property
    def _conflicts(self) -> Conflicts:
        return self._selection.conflicts

    def nodes(self) -> tuple[str, ...]:
        """The nodes placed so far, in the order they were placed."""

        return self._relationships.get_used_nodes()

    def is_satisfied(self) -> bool:
        """Whether everything the projection demanded has been placed."""

        return self._conflicts.is_satisfied()

    def _supplies(self, node: str, column: str) -> bool:
        table = self._schema.tables.get(unqualify(node)[0])

        return table is not None and column in table.fields

    def _admits(self, node: str) -> bool:
        """Whether placing `node` leaves every bare column with one supplier."""

        return not any(
            self._supplies(node, column)
            and any(self._supplies(placed, column) for placed in self.nodes())
            for column in self._selection.projection.bare_columns()
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

    def join(self, neighbor: Neighbor, join_type: JoinType) -> bool:
        """Join `neighbor` into the current entry, satisfying it if required."""

        if neighbor not in self.neighbors():
            return False

        if neighbor.table in self._conflicts.get_required_tables():
            self._conflicts.use_table(neighbor.table)

        return self._relationships.join_table(neighbor, join_type)

    def __str__(self) -> str:
        return str(self._relationships)
