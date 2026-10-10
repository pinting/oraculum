"""Generation state shared by the nodes of the syntax graph.

A context is what a node of the graph carries: the statement as far as it has
been written. That is

* the **stack** of virtual tables closed so far, as a `Catalog` - the `WITH`
  definitions, each one readable by everything after it;
* the **query** being written, a `VirtualTable` over that stack, or nothing
  between two definitions;
* the statement machine of `state.statement`, which says which of those is
  open.

Everything about the data structure of a query is its virtual table's
business. The context only opens queries, and pushes a closed definition onto
the stack it hands to the next one.

Everything a thunk asks is ordered and side effect free, and everything a
selector applies happens on a `copy()`, so branches never see each other. A
copy copies the open query alone: the stack below it is closed, so it is shared.

Every operation that modifies the statement traces the whole resolver state.
See `debug.py`; tracing is off until a driver enables it.
"""

from __future__ import annotations

from . import debug
from .model import Schema
from .query import Catalog, Exclusion, VirtualTable
from .state import Machine, Phase, statement_machine

class Context:
    __slots__ = ("_phase", "_catalog", "_query")

    def __init__(self, schema: Schema | None = None) -> None:
        if schema is None:
            return

        self._phase: Machine[Phase] = statement_machine()
        self._catalog: Catalog = Catalog(schema)
        self._query: VirtualTable | None = None

    def copy(self) -> "Context":
        clone: Context = Context.__new__(Context)

        clone._phase = self._phase
        clone._catalog = self._catalog
        clone._query = None if self._query is None else self._query.copy()

        return clone

    @property
    def schema(self) -> Schema:
        """The schema as declared."""

        return self._catalog.physical

    @property
    def phase(self) -> Phase:
        return self._phase.state

    @property
    def catalog(self) -> Catalog:
        """The stack of definitions closed so far."""

        return self._catalog

    @property
    def query(self) -> VirtualTable:
        """The query being written; there is one wherever the grammar asks."""

        assert self._query is not None, f"no query is open in the {self.phase.value}"

        return self._query

    def _enter(self, phase: Phase) -> bool:
        advanced: Machine[Phase] | None = self._phase.advance(phase)

        if advanced is None or advanced is self._phase:
            return False

        self._phase = advanced

        return True

    # -- definitions ------------------------------------------------------

    def get_reserved_names(self) -> Exclusion:
        """What a definition's name may not spell: anything the stack defines."""

        return self._catalog.reserved

    @debug.traced(lambda self, name: f"begin_definition({name})")
    def begin_definition(self, name: str) -> bool:
        """Open the query of `WITH <name> AS (...)`."""

        if not self._catalog.reserved.allows(name) or not self._enter(Phase.DEFINITION):
            return False

        self._query = VirtualTable(self._catalog, name)

        return True

    @debug.traced(lambda self: "end_definition()")
    def end_definition(self) -> bool:
        """Close the open definition and push it onto the stack."""

        if self._query is None or not self._phase.is_at(Phase.DEFINITION):
            return False

        if not self._query.close() or not self._enter(Phase.PREAMBLE):
            return False

        self._catalog = self._catalog.push(self._query)
        self._query = None

        return True

    # -- the main query ---------------------------------------------------

    @debug.traced(lambda self: "begin_main()")
    def begin_main(self) -> bool:
        """Open the main query, over every definition closed so far."""

        if not self._enter(Phase.MAIN):
            return False

        self._query = VirtualTable(self._catalog)

        return True

    def __str__(self) -> str:
        query: str = "" if self._query is None else f"\n{self._query}"

        return f"Statement        = {self._phase}\nStack            = {self._catalog}{query}"

    def __repr__(self) -> str:
        return f"Context(phase={self.phase.name}, query={self._query!r})"
