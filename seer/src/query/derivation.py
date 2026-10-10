"""The table a closed query exports, once it is stacked under another.

A derived table is a `Table` like any the schema declared, so everything that
reads tables - the resolvers, the join graph, the relation - reads it without
knowing it was derived. Its columns are the projection's items, by output
name:

* a plain column keeps what its source column was: type, foreign key and
  origin, so a join can still follow it. It loses being a key - a join or a
  grouping may have repeated its values - and keeps being NULL only where its
  source could be;
* an aggregate is the column its function produces over the source column,
  with no origin, since it is a computed value and no schema column at all.
"""

from __future__ import annotations

from ..model import Field, Table, is_nullable
from .projection import Item, Projection
from .relation import Operand, Relation

def _source(relation: Relation, item: Item) -> Field | None:
    if item.reference is None:
        return None

    operand: Operand | None = relation.resolve(item.reference)

    assert operand is not None, f"{item.reference} does not resolve in the closed relation"

    return operand.field

def _column(relation: Relation, item: Item, name: str) -> Field:
    source: Field | None = _source(relation, item)

    if item.function is not None:
        return item.function.apply(source, name)

    assert source is not None

    return Field(
        name=name,
        type=source.type,
        is_nullable=is_nullable(source),
        reference=source.reference,
        origin=source.origin,
    )

def derive(projection: Projection, relation: Relation) -> Table:
    """The table `projection` produces over `relation`."""

    table: Table = Table()

    for item in projection.items:
        name: str | None = item.output

        assert name is not None, f"{item} has no name to export under"
        assert name not in table.fields, f"{name} is exported twice"

        table.fields[name] = _column(relation, item, name)

    return table
