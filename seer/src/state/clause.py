"""The lifecycle of one SELECT, clause by clause.

A query is written in a fixed order and each clause is resolved against a
different structure, so which clause is open decides what may be asked:

    PROJECTION -> SOURCE -> [FILTER] -> [GROUPING -> [HAVING]] -> CLOSED

* **PROJECTION** - items are being selected; the conflicts narrow the tables.
* **SOURCE** - the `FROM` keyword has been taken; the join graph is built over
  whatever the projection ended up requiring, and entries and joins are placed.
* **FILTER** - `WHERE`; the FROM clause is closed and conditions are written
  against the relation it produced.
* **GROUPING** - `GROUP BY`; columns of that relation are grouped on.
* **HAVING** - conditions over the grouped columns and aggregates.
* **CLOSED** - the query has ended, at its terminator or its closing bracket.

Every clause after SOURCE reads the closed relation, so leaving SOURCE - for
whichever of them - is where it is built. Each boundary falls on a token, and a
boundary is the only place a structure is built.
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
    CLOSED = "closed"

TRANSITIONS: Transitions[Clause] = validate({
    Clause.PROJECTION: frozenset({Clause.SOURCE}),
    Clause.SOURCE: frozenset({Clause.FILTER, Clause.GROUPING, Clause.CLOSED}),
    Clause.FILTER: frozenset({Clause.GROUPING, Clause.CLOSED}),
    Clause.GROUPING: frozenset({Clause.HAVING, Clause.CLOSED}),
    Clause.HAVING: frozenset({Clause.CLOSED}),
    Clause.CLOSED: frozenset(),
}, Clause)

def clause_machine() -> Machine[Clause]:
    return Machine(TRANSITIONS, Clause.PROJECTION)
