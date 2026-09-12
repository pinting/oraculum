"""FROM / JOIN resolution over the foreign key graph.

Once `conflicts.py` knows which tables the query needs, they have to be
connected by foreign keys. Nodes are table names -- including aliased variants
such as `"comments c"` -- and edges are the foreign keys between them, carrying
the column pair the `ON` clause is written from.

Joining merges the neighbour into the head via SageMath's `merge_vertices`, so
the head's neighbourhood becomes the union of both. That models SQL: once two
tables are joined, every column of either is reachable, and the pair behaves as
one node for further joins.

Neighbour queries answer with sorted tuples rather than sets, because the
syntax graph must expand the same way on every run.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, NamedTuple

from sage.all import Graph

from .schema import Schema
from .scopes import sql_name, unqualify

def reference_name(node: str) -> str:
    """How a node is written in an `ON` clause.

    These tokens are emitted verbatim, so they have to be valid SQL: an aliased
    node is referenced by its alias and a bare one by its table name.
    """

    table, alias = unqualify(node)

    return alias if alias else table

class JoinType(Enum):
    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"
    FULL = "FULL JOIN"

    def __str__(self) -> str:
        return self.value

JOIN_TYPES: list[JoinType] = list(JoinType)

class Neighbor(NamedTuple):
    table: str
    src_field: str
    dst_field: str

    def __str__(self) -> str:
        return f"{self.table} ON {self.src_field} = {self.dst_field}"

    def format(self, join_type: JoinType = JoinType.INNER) -> str:
        """The clause as SQL, so an aliased node gets its `AS`."""

        return f"{join_type} {sql_name(self.table)} ON {self.src_field} = {self.dst_field}"

@dataclass(frozen=True)
class FieldRef:
    node: str
    field: str

@dataclass(frozen=True)
class EdgeLabel:
    src: FieldRef
    dst: FieldRef

    def orient(self, head_node: str, neighbor_node: str) -> Neighbor:
        """Point the edge away from the head, so `src` is the head's column."""

        if self.src.node == head_node or self.dst.node == neighbor_node:
            return Neighbor(neighbor_node, self.src.field, self.dst.field)

        return Neighbor(neighbor_node, self.dst.field, self.src.field)

class JoinGraph:
    """A thin wrapper over SageMath's multigraph.

    It exists only to keep the vertex and edge vocabulary of this module in one
    place, and to give `Relationships` a `copy()` so each branch of the syntax
    graph can merge vertices without disturbing its siblings.
    """

    __slots__ = ("_graph",)

    def __init__(self, edges: Iterable[tuple[str, str, EdgeLabel]] | None = None) -> None:
        self._graph: Any = Graph(list(edges or ()), multiedges=True)

    @property
    def unit(self) -> Any:
        return self._graph

    def copy(self) -> "JoinGraph":
        clone: JoinGraph = JoinGraph.__new__(JoinGraph)

        clone._graph = self._graph.copy()

        return clone

    def __contains__(self, node: str) -> bool:
        return node in self._graph

    def nodes(self) -> list[str]:
        return sorted(str(vertex) for vertex in self._graph.vertices())

    def edges(self, node: str) -> list[tuple[str, EdgeLabel]]:
        """Every edge incident to `node`, as `(neighbour, label)`."""

        if node not in self._graph:
            return []

        incident: list[tuple[str, EdgeLabel]] = []

        for source, target, label in self._graph.edges(node, labels=True):
            incident.append((target if source == node else source, label))

        return incident

    def merge_vertices(self, head: str, other: str) -> None:
        """Fold `other` into `head`."""

        if head == other or other not in self._graph or head not in self._graph:
            return

        self._graph.merge_vertices([head, other])

class Relationships:
    """The FROM clause: pick a required table, then walk the foreign keys."""

    __slots__ = ("_schema", "_graph", "_head", "_used_references")

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
        self._graph = JoinGraph(self._build_edges(schema, required))

    @staticmethod
    def _build_edges(
        schema: Schema,
        required: Iterable[str],
    ) -> list[tuple[str, str, EdgeLabel]]:
        nodes: list[str] = sorted(set(schema.tables.keys()) | set(required))
        edges: list[tuple[str, str, EdgeLabel]] = []

        for i, first in enumerate(nodes):
            for second in nodes[i + 1:]:
                first_table, _ = unqualify(first)
                second_table, _ = unqualify(second)

                left = schema.tables.get(first_table)
                right = schema.tables.get(second_table)

                if left is None or right is None:
                    continue

                first_ref: str = reference_name(first)
                second_ref: str = reference_name(second)

                for column in left.references(second_table):
                    assert column.reference is not None

                    edges.append((first, second, EdgeLabel(
                        src=FieldRef(first, f"{first_ref}.{column.name}"),
                        dst=FieldRef(second, f"{second_ref}.{column.reference.column}"),
                    )))

                for column in right.references(first_table):
                    assert column.reference is not None

                    edges.append((first, second, EdgeLabel(
                        src=FieldRef(second, f"{second_ref}.{column.name}"),
                        dst=FieldRef(first, f"{first_ref}.{column.reference.column}"),
                    )))

        return edges

    def copy(self) -> "Relationships":
        clone: Relationships = Relationships.__new__(Relationships)

        clone._schema = self._schema
        clone._graph = self._graph.copy()
        clone._head = self._head
        clone._used_references = self._used_references

        return clone

    @property
    def head(self) -> str | None:
        return self._head

    @property
    def graph(self) -> JoinGraph:
        return self._graph

    def get_used_references(self) -> tuple[str, ...]:
        return self._used_references

    def use_table(self, node: str) -> bool:
        """Open a new FROM entry at `node`, which becomes the head."""

        self._head = node
        self._used_references = self._used_references + (sql_name(node),)

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

        if self._used_references:
            joined: str = f"{self._used_references[-1]} {neighbor.format(join_type)}"

            self._used_references = self._used_references[:-1] + (joined,)

        return True

    def __str__(self) -> str:
        return ", ".join(self._used_references)

    def __repr__(self) -> str:
        return f"Relationships(head={self._head!r})"
