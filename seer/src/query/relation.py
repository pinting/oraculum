"""The relation a closed FROM clause produces.

Up to the `FROM` keyword the modelling runs forwards: `Conflicts` decides which
tables the selected fields demand and `Relationships` connects them by
contracting the foreign key graph. A WHERE clause runs the other way. Its FROM
clause is already closed, so the columns a filter may name are not a constraint
to be solved - they are a fixed set, the one relation the entries and their
joins produced. Building it is what leaving the SOURCE clause does.

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
`operators.py` gates the conditions on. A function over operands is an operand
too, of the type it produces, which is what a HAVING condition compares and a
GROUP BY may key on.

Every operand has a **key**, the value it is regardless of spelling. A column
is keyed by its node, so `email` and `users.email` are one key; a call by its
function and its arguments' keys. The projection's expressions render to the
same keys (`Relation.key`), which is how grouping tells whether an item is a
grouped value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Mapping

from ..model import Field, Schema, Table, TypeClass, column_name, reference_name, unqualify
from .operand import Operand

if TYPE_CHECKING:
    from .expression import Column

class Relation:
    """The columns a closed FROM clause offers, and how each may be spelled.

    Immutable once built, so every branch that copies a query shares it.
    """

    __slots__ = ("_nodes", "_operands", "_by_text")

    def __init__(
        self,
        schema: Schema | None = None,
        nodes: Iterable[str] = (),
        nullable: frozenset[str] = frozenset(),
        derived: Mapping[str, Table] | None = None,
    ) -> None:
        if schema is None:
            return

        # A node cannot appear twice in one FROM clause, but the record is
        # accumulated across entries, so it is deduplicated in order rather
        # than trusted.
        self._nodes: tuple[str, ...] = tuple(dict.fromkeys(nodes))
        self._operands = self._build_operands(schema, self._nodes, nullable, derived or {})
        self._by_text: dict[str, Operand] = {operand.text: operand for operand in self._operands}

    @staticmethod
    def _build_operands(
        schema: Schema,
        nodes: tuple[str, ...],
        nullable: frozenset[str],
        derived: Mapping[str, Table],
    ) -> tuple[Operand, ...]:
        """Every way a column of the clause may be named, sorted by spelling.

        A column of a node an outer join pads is NULL wherever the join found
        no partner, whatever the schema says of it.
        """

        operands: list[Operand] = []
        owners: dict[str, list[tuple[str, Field]]] = {}

        for node in nodes:
            name, _ = unqualify(node)
            table: Table | None = derived.get(node, schema.tables.get(name))

            if table is None:
                continue

            qualifier: str = reference_name(node)

            for column, field in table.fields.items():
                if node in nullable:
                    field = field.optional()

                operands.append(Operand.column(node, column, column_name(qualifier, column), field))
                owners.setdefault(column, []).append((node, field))

        for column, supplying in owners.items():
            # Two nodes carrying the column make the bare name ambiguous, and
            # SQL refuses it outright rather than picking one.
            if len(supplying) != 1:
                continue

            node, field = supplying[0]

            operands.append(Operand.column(node, column, column, field))

        return tuple(sorted(operands, key=lambda operand: operand.text))

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

        return tuple(operand for operand in self._operands if operand.kind is kind)

    def resolve(self, text: str) -> Operand | None:
        """The column a spelling names here, or `None` where it names nothing.

        A bare name two nodes supply is not an operand, so it resolves to
        nothing, which is SQL's own answer.
        """

        return self._by_text.get(text)

    def operand(self, column: "Column") -> Operand:
        """The operand a column of the projection is, now the clause is closed.

        Every column the projection named resolves: a bare name two nodes
        would supply was never offered, and FROM placed what each demanded.
        """

        operand: Operand | None = self.resolve(column.text)

        assert operand is not None, f"{column.text} does not resolve in the closed relation"

        return operand

    def field(self, column: "Column") -> Field:
        return self.operand(column).field

    def key(self, column: "Column") -> str:
        return self.operand(column).key

    def get_names(self) -> tuple[str, ...]:
        """Every spelling on offer, which is what a thunk turns into lattices."""

        return tuple(operand.text for operand in self._operands)

    def __repr__(self) -> str:
        return f"Relation(nodes={list(self._nodes)})"
