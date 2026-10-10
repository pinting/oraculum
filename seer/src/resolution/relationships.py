"""FROM / JOIN resolution: walking the foreign key graph of `joins.py`.

Once `conflicts.py` knows which tables the query needs, they have to be
connected by foreign keys.

Joining merges the neighbour into the head via the graph's `merge_vertices`, so
the head's neighbourhood becomes the union of both. That models SQL: once two
tables are joined, every column of either is reachable, and the pair behaves as
one node for further joins.

Neighbour queries answer with sorted tuples rather than sets, because the
syntax graph must expand the same way on every run.
"""

from __future__ import annotations

from typing import Iterable

from ..model import Schema, sql_name
from ..runtime import JoinGraph
from .joins import JoinType, Neighbor, edges

class Relationships:
    """The FROM clause: pick a required table, then walk the foreign keys."""

    __slots__ = ("_schema", "_graph", "_head", "_used_references", "_used_nodes")

    def __init__(
        self,
        schema: Schema | None = None,
        required: Iterable[str] = (),
    ) -> None:
        if schema is None:
            return

        self._schema = schema
        self._head: str | None = None
        self._used_references: tuple[str, ...] = ()
        self._used_nodes: tuple[str, ...] = ()
        self._graph = JoinGraph(edges(schema, required))

    def copy(self) -> "Relationships":
        clone: Relationships = Relationships.__new__(Relationships)

        clone._schema = self._schema
        clone._graph = self._graph.copy()
        clone._head = self._head
        clone._used_references = self._used_references
        clone._used_nodes = self._used_nodes

        return clone

    @property
    def head(self) -> str | None:
        return self._head

    @property
    def graph(self) -> JoinGraph:
        return self._graph

    def get_used_references(self) -> tuple[str, ...]:
        return self._used_references

    def get_used_nodes(self) -> tuple[str, ...]:
        """Every node the clause has placed, as `"table"` or `"table alias"`.

        `_used_references` is the same history rendered as SQL, which is what
        the debug block prints; this is the structural half, and it is what the
        closed relation of `query.relation` is built over. Contraction destroys the
        vertices as it goes, so the record has to be kept rather than read back
        off the graph.
        """

        return self._used_nodes

    def use_table(self, node: str) -> bool:
        """Open a new FROM entry at `node`, which becomes the head."""

        self._head = node
        self._used_references = self._used_references + (sql_name(node),)
        self._used_nodes = self._used_nodes + (node,)

        return True

    def get_joinable_neighbors(self, excluded: frozenset[str] = frozenset()) -> tuple[Neighbor, ...]:
        """Neighbours of the head that are not excluded, in a stable order."""

        if self._head is None or self._head not in self._graph:
            return ()

        joinable: set[Neighbor] = set()

        for neighbor_node, label in self._graph.edges(self._head):
            neighbor: Neighbor = label.orient(self._head, neighbor_node)

            if neighbor.table in excluded:
                continue

            joinable.add(neighbor)

        return tuple(sorted(joinable))

    def join_table(self, neighbor: Neighbor, join_type: JoinType = JoinType.INNER) -> bool:
        """Merge `neighbor` into the head and record the join."""

        if self._head is None:
            return False

        self._graph.merge_vertices(self._head, neighbor.table)

        self._used_nodes = self._used_nodes + (neighbor.table,)

        if self._used_references:
            joined: str = f"{self._used_references[-1]} {neighbor.format(join_type)}"

            self._used_references = self._used_references[:-1] + (joined,)

        return True

    def __str__(self) -> str:
        return ", ".join(self._used_references)

    def __repr__(self) -> str:
        return f"Relationships(head={self._head!r})"
