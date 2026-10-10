"""The edges of the join graph, and the values a join is described by.

Nodes are table names - including aliased variants such as `"comments c"` -
and an edge is a foreign key between two of them, labelled with the column
pair the `ON` clause is written from. A key matches its target by origin (see
`Table.links`), so a derived table that projected `posts.user_id` still joins
`users`, and one that projected `users.id` is still joined by `posts`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, NamedTuple

from ..model import Schema, Table, column_name, reference_name, sql_name, unqualify

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

Edge = tuple[str, str, EdgeLabel]

def _labels(src: str, src_table: Table, dst: str, dst_table: Table) -> list[EdgeLabel]:
    """Every foreign key from a column of `src` to a column of `dst`."""

    src_ref: str = reference_name(src)
    dst_ref: str = reference_name(dst)

    return [
        EdgeLabel(
            src=FieldRef(src, column_name(src_ref, key.name)),
            dst=FieldRef(dst, column_name(dst_ref, target.name)),
        )
        for key, target in src_table.links(dst_table)
    ]

def edges(schema: Schema, required: Iterable[str]) -> list[Edge]:
    """The join graph over every table of `schema` and every required node."""

    nodes: list[str] = sorted(set(schema.tables.keys()) | set(required))
    result: list[Edge] = []

    for i, first in enumerate(nodes):
        for second in nodes[i + 1:]:
            left: Table | None = schema.tables.get(unqualify(first)[0])
            right: Table | None = schema.tables.get(unqualify(second)[0])

            if left is None or right is None:
                continue

            for label in _labels(first, left, second, right) + _labels(second, right, first, left):
                result.append((first, second, label))

    return result
