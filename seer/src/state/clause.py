"""The lifecycle of one SELECT, clause by clause.

A query is written in a fixed order and each clause is resolved against a
different structure, so which clause is open decides what may be asked:

    PROJECTION -> SOURCE -> [FILTER] -> [GROUPING -> [HAVING]]      the body
               -> [ORDERING] -> [LIMITING] -> CLOSED                the presentation

* **PROJECTION** - items are being selected; the conflicts narrow the tables.
* **SOURCE** - the `FROM` keyword has been taken; the join graph is built over
  whatever the projection ended up requiring, and entries and joins are placed.
* **FILTER** - `WHERE`; the FROM clause is closed and conditions are written
  against the relation it produced.
* **GROUPING** - `GROUP BY`; values of that relation are grouped on.
* **HAVING** - conditions over the grouped values and aggregates.
* **ORDERING** - `ORDER BY`; the result is complete, and is sorted.
* **LIMITING** - `LIMIT [OFFSET]`.
* **CLOSED** - the query has ended: at its terminator, its closing bracket, or
  the set operator that starts the next member of a compound.

Every clause after SOURCE reads the closed relation, so leaving SOURCE - for
whichever of them - is where it is built. Leaving the body - for ORDERING,
LIMITING or CLOSED - is where the result has to be complete, which is the one
rule that spans clauses and is the virtual table's to check. Each boundary
falls on a token, and a boundary is the only place a structure is built.
"""

from __future__ import annotations

from enum import Enum

from .machine import Machine, Transitions, validate

class Clause(Enum):
    PROJECTION = "projection"
    SOURCE = "source"
    FILTER = "filter"
    GROUPING = "grouping"
    HAVING = "having"
    ORDERING = "ordering"
    LIMITING = "limiting"
    CLOSED = "closed"

# The clauses a query may end its body in, and the ones after it.
BODY: frozenset[Clause] = frozenset({Clause.SOURCE, Clause.FILTER, Clause.GROUPING, Clause.HAVING})
PRESENTATION: frozenset[Clause] = frozenset({Clause.ORDERING, Clause.LIMITING, Clause.CLOSED})

TRANSITIONS: Transitions[Clause] = validate({
    Clause.PROJECTION: frozenset({Clause.SOURCE}),
    Clause.SOURCE: frozenset({Clause.FILTER, Clause.GROUPING}) | PRESENTATION,
    Clause.FILTER: frozenset({Clause.GROUPING}) | PRESENTATION,
    Clause.GROUPING: frozenset({Clause.HAVING}) | PRESENTATION,
    Clause.HAVING: PRESENTATION,
    Clause.ORDERING: frozenset({Clause.LIMITING, Clause.CLOSED}),
    Clause.LIMITING: frozenset({Clause.CLOSED}),
    Clause.CLOSED: frozenset(),
}, Clause)

def clause_machine() -> Machine[Clause]:
    return Machine(TRANSITIONS, Clause.PROJECTION)
