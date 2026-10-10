"""The state machines, kept apart from the work their transitions trigger.

    machine.py        a finite state machine as an immutable value
    statement.py      the lifecycle of a statement: definitions, then the main query
    clause.py         the lifecycle of one SELECT, clause by clause
"""

from .clause import Clause, clause_machine
from .machine import Machine, Transitions
from .statement import Phase, statement_machine

__all__ = [
    "Clause",
    "Machine",
    "Phase",
    "Transitions",
    "clause_machine",
    "statement_machine",
]
