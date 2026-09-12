"""The virtual table a FROM clause produces.

Up to the `FROM` keyword the modelling runs forwards: `Conflicts` decides which
tables the selected fields demand and `Relationships` connects them by
contracting the foreign key graph. A WHERE clause runs the other way. Its FROM
clause is already closed, so the columns a filter may name are not a constraint
to be solved - they are a fixed set, the one relation the entries and their
joins produced. Building it is what `Context.enter_where` does, and it is the
second and last phase boundary of a statement.

Closing the clause makes the two things SQL leaves to a resolver decidable by
counting:

* a column is always reachable **qualified**, by its node's reference name -
  the alias where the node carries one, the table name otherwise;
* it is reachable **bare** exactly when one node in the clause supplies that
  name, which is SQL's own ambiguity rule and now a question about a finite
  set rather than about the schema.

Nothing else about the FROM clause survives here. Two tables joined are one
relation and their columns sit side by side in it, so a filter cannot tell a
static source from a dynamic one - which is the point.

An `Operand` is one such column, together with how it is written and the
`Field` it came from. The field is what carries the type, and the type is what
`operators.py` gates the conditions on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .operators import TypeClass, classify
from .schema import Field, Schema
from .scopes import reference_name, unqualify

@dataclass(frozen=True)
class Operand:
    """One column of the virtual table, and how a condition names it."""

    node: str
    """The FROM node it came from, `"users"` or `"users u"`."""

    name: str
    """The column name, unqualified."""

    text: str
    """How it is written: `"email"` bare, `"u.email"` qualified."""

    field: Field
    """The schema column, which is what carries the type."""

    def same_column(self, other: "Operand") -> bool:
        """Whether both name the same column, however each is spelled."""

        return self.node == other.node and self.name == other.name

    def __str__(self) -> str:
        return self.text

class Relation:
    """The columns a WHERE clause may filter on, and the filters written so far."""

    __slots__ = ("_schema", "_nodes", "_operands", "_used_filters")

    def __init__(self, schema: Schema | None = None, nodes: Iterable[str] = ()) -> None:
        if schema is None:
            return

        # A node cannot appear twice in one FROM clause, but the record is
        # accumulated across entries, so it is deduplicated in order rather
        # than trusted.
        self._schema = schema
        self._nodes: tuple[str, ...] = tuple(dict.fromkeys(nodes))
        self._operands = self._build_operands(schema, self._nodes)
        self._used_filters: tuple[str, ...] = ()

    @staticmethod
    def _build_operands(schema: Schema, nodes: tuple[str, ...]) -> tuple[Operand, ...]:
        """Every way a column of the clause may be named, sorted by spelling."""

        operands: list[Operand] = []
        owners: dict[str, list[tuple[str, Field]]] = {}

        for node in nodes:
            name, _ = unqualify(node)
            table = schema.tables.get(name)

            if table is None:
                continue

            qualifier: str = reference_name(node)

            for column, field in table.fields.items():
                operands.append(Operand(node, column, f"{qualifier}.{column}", field))
                owners.setdefault(column, []).append((node, field))

        for column, supplying in owners.items():
            # Two nodes carrying the column make the bare name ambiguous, and
            # SQL refuses it outright rather than picking one.
            if len(supplying) != 1:
                continue

            node, field = supplying[0]

            operands.append(Operand(node, column, column, field))

        return tuple(sorted(operands, key=lambda operand: operand.text))

    def copy(self) -> "Relation":
        clone: Relation = Relation.__new__(Relation)

        clone._schema = self._schema
        clone._nodes = self._nodes
        clone._operands = self._operands
        clone._used_filters = self._used_filters

        return clone

    @property
    def schema(self) -> Schema:
        return self._schema

    def get_nodes(self) -> tuple[str, ...]:
        """The FROM nodes the relation was built over."""

        return self._nodes

    def get_operands(self, kind: TypeClass | None = None) -> tuple[Operand, ...]:
        """Every operand, or only those of one type class.

        Ordered by spelling, so the syntax graph expands the same way on every
        run however the schema happened to be written.
        """

        if kind is None:
            return self._operands

        return tuple(
            operand
            for operand in self._operands
            if classify(operand.field.type) is kind
        )

    def get_names(self) -> tuple[str, ...]:
        """Every spelling on offer, which is what a thunk turns into lattices."""

        return tuple(operand.text for operand in self._operands)

    def get_used_filters(self) -> tuple[str, ...]:
        return self._used_filters

    def use_filter(self, text: str) -> bool:
        """Record a condition, once it has been written whole."""

        if not text:
            return False

        self._used_filters = self._used_filters + (text,)

        return True

    def __str__(self) -> str:
        return ", ".join(self._used_filters)

    def __repr__(self) -> str:
        return f"Relation(nodes={list(self._nodes)})"
