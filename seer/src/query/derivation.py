"""The columns a closed query produces, and the table a definition exports.

A closed query's **result** is one `Output` per item, in order: the name the
item goes by, if it has one, and the `Field` it is. A derived table is a
`Table` like any the schema declared, so everything that reads tables - the
resolvers, the join graph, the relation - reads it without knowing it was
derived. Its columns are the result's:

* a plain column keeps what its source column was: type, foreign key and
  origin, so a join can still follow it. It loses being a key - a join or a
  grouping may have repeated its values - and keeps being NULL only where its
  source could be, which an outer join may have made it;
* anything computed is the column its expression produces (`Expr.field`),
  with no origin, since it is no schema column at all.

A compound query's result is its members' merged: named by the first member,
NULL wherever any member may be, and keeping a lineage only where every member
agrees on the column its values come from. A member's column either *is* a
schema column (its origin) or *points at* one (its reference), and either way
its values are that column's. So

* where every member agrees on both, the merged column keeps both;
* where they only agree on whose values they hold - `users.id` in one member,
  `posts.user_id` in the next - the merged column holds that column's values:
  it is a projection of it if any member was, and points at it if every one
  did;
* where they disagree, it is a computed column with no lineage at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..model import Field, Reference, Table, is_nullable
from .expression import Column, Expr
from .projection import Projection
from .relation import Relation

@dataclass(frozen=True)
class Output:
    name: str | None
    field: Field

Result = tuple[Output, ...]

def _column(relation: Relation, expr: Expr) -> Field:
    if not isinstance(expr, Column):
        return expr.field(relation.field)

    source: Field = relation.field(expr)

    return Field(
        name=expr.name,
        type=source.type,
        is_nullable=is_nullable(source),
        reference=source.reference,
        origin=source.origin,
    )

def result(projection: Projection, relation: Relation) -> Result:
    """What `projection` produces over `relation`, item by item."""

    return tuple(Output(item.output, _column(relation, item.expr)) for item in projection.items)

def _lineage(fields: Sequence[Field]) -> tuple[Reference | None, Reference | None]:
    """The `(origin, reference)` of a column merged from `fields`."""

    first: Field = fields[0]

    if all(field.origin == first.origin and field.reference == first.reference for field in fields):
        return first.origin, first.reference

    domains: set[Reference | None] = {field.reference or field.origin for field in fields}

    if len(domains) != 1 or None in domains:
        return None, None

    domain: Reference | None = domains.pop()

    if all(field.reference == domain for field in fields):
        return None, domain

    return domain, None

def merge(results: Sequence[Result]) -> Result:
    """The result of a compound of `results`, which all have the same arity."""

    first: Result = results[0]

    assert all(len(other) == len(first) for other in results), "members of different arity"

    merged: list[Output] = []

    for position, output in enumerate(first):
        fields: list[Field] = [other[position].field for other in results]
        origin, reference = _lineage(fields)

        merged.append(Output(output.name, Field(
            name=output.field.name,
            type=output.field.type,
            is_nullable=any(is_nullable(field) for field in fields),
            reference=reference,
            origin=origin,
        )))

    return tuple(merged)

def table(result: Result, names: Sequence[str] = ()) -> Table:
    """The table `result` exports, its columns called `names` where given."""

    exported: Table = Table()

    for position, output in enumerate(result):
        name: str | None = names[position] if names else output.name

        assert name is not None, f"column {position + 1} has no name to export under"
        assert name not in exported.fields, f"{name} is exported twice"

        field: Field = output.field

        exported.fields[name] = Field(
            name=name,
            type=field.type,
            is_nullable=field.is_nullable,
            reference=field.reference,
            origin=field.origin,
        )

    return exported
