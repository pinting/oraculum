"""The lifecycle of a statement: definitions first, then the main query.

    PREAMBLE -> DEFINITION -> PREAMBLE -> ... -> MAIN

* **PREAMBLE** - no query is open. What comes next is either another `WITH`
  definition or the main `SELECT`.
* **DEFINITION** - a `WITH` definition's query is open. Closing it pushes it
  onto the stack and goes back to the preamble.
* **MAIN** - the main query is open, and the statement ends with it.

The clause machine of `clause.py` runs inside each open query; this one only
says which query is open, and whether one may be opened at all.
"""

from __future__ import annotations

from enum import Enum

from .machine import Machine, Transitions, validate

class Phase(Enum):
    PREAMBLE = "preamble"
    DEFINITION = "definition"
    MAIN = "main"

TRANSITIONS: Transitions[Phase] = validate({
    Phase.PREAMBLE: frozenset({Phase.DEFINITION, Phase.MAIN}),
    Phase.DEFINITION: frozenset({Phase.PREAMBLE}),
    Phase.MAIN: frozenset(),
}, Phase)

def statement_machine() -> Machine[Phase]:
    return Machine(TRANSITIONS, Phase.PREAMBLE)
