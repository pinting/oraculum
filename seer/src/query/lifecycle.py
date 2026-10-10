"""The rules that decide whether a query may move from one clause to the next.

The clause machine (`state.clause`) says which moves exist; these say which of
them the query may make, which is where the rules that span parts live:

* the projection has to be complete before FROM - as many items as its shape
  asks for, each named where its frame needs names;
* the body has to be complete before anything after it - the FROM clause
  placing everything the projection demanded, and the grouping covering every
  item of a query that aggregates;
* a recursive member stays a simple select, so it never groups, sorts or
  limits;
* a scalar subquery is one row, so it never groups.

They are pure functions of the query's parts, so the virtual table asks them
and nothing else has to know how the parts fit.
"""

from __future__ import annotations

from ..state import BODY, PRESENTATION, Clause, Machine
from .frame import Frame
from .grouping import Grouping
from .refinement import Refinement
from .selection import Selection
from .sources import Sources

# The clauses a recursive member may not reach: it has to stay a simple select.
NOT_SIMPLE: frozenset[Clause] = frozenset({
    Clause.GROUPING, Clause.HAVING, Clause.ORDERING, Clause.LIMITING,
})

def body_is_complete(
    selection: Selection,
    sources: Sources | None,
    refinement: Refinement | None,
) -> bool:
    """Whether the result is complete: FROM supplies everything, grouping covers it."""

    if sources is None or not sources.nodes() or not sources.is_satisfied():
        return False

    projection = selection.projection

    # Still in SOURCE, nothing is grouped yet; whether anything had to be
    # needs no relation, since an empty grouping covers constants and
    # aggregates only.
    if refinement is None:
        return not projection.has_aggregates() or all(
            Grouping().covers(item.expr, lambda _: "") for item in projection.items
        )

    return refinement.covers(projection)

def may_enter(
    clause: Clause,
    machine: Machine[Clause],
    frame: Frame,
    selection: Selection,
    sources: Sources | None,
    refinement: Refinement | None,
) -> bool:
    """Whether a query standing at `machine` may move to `clause`."""

    if machine.is_at(clause):
        return True

    if not machine.can_advance(clause):
        return False

    if frame.recursive and clause in NOT_SIMPLE:
        return False

    # A value is one row, which grouping would break into many.
    if clause is Clause.GROUPING and selection.contract.single_row:
        return False

    if clause is Clause.SOURCE:
        return selection.is_complete()

    if clause in PRESENTATION and machine.state in BODY:
        return body_is_complete(selection, sources, refinement)

    return True
