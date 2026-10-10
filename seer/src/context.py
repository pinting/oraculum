"""Generation state shared by the nodes of the syntax graph.

A context is what a node of the graph carries: the statement as far as it has
been written. That is

* the **stack** of virtual tables closed so far, as a `Catalog` - the `WITH`
  definitions, each one readable by everything after it;
* the **declaration** being written, between a definition's name and the
  `SELECT` of its body - its name and its column list;
* the **query** being written, a `VirtualTable` over that stack, or nothing
  between two definitions. A compound query is written one member at a time,
  so this is the member being written, which holds the ones before it;
* the statement machine of `state.statement`, which says which of those is
  open, and whether the statement is `WITH RECURSIVE`;
* the **capture**, the text of the last token a selector set aside for the one
  that commits it - the first bound of a `BETWEEN`, the values of an `IN`, a
  literal the projection is about to wrap in an expression. Nothing reads it
  but the selector it was set aside for.

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

from dataclasses import dataclass, replace

from . import debug
from .model import Schema
from .query import Catalog, Exclusion, Frame, SetOperator, VirtualTable
from .state import Machine, Phase, statement_machine

@dataclass(frozen=True)
class Declaration:
    """A definition as far as it has been declared: `<name> [( <column>, ... )]`."""

    name: str
    columns: tuple[str, ...] = ()

class Context:
    __slots__ = ("_phase", "_recursive", "_catalog", "_declaration", "_query", "_capture")

    def __init__(self, schema: Schema | None = None) -> None:
        if schema is None:
            return

        self._phase: Machine[Phase] = statement_machine()
        self._recursive: bool = False
        self._catalog: Catalog = Catalog(schema)
        self._declaration: Declaration | None = None
        self._query: VirtualTable | None = None
        self._capture: str = ""

    def copy(self) -> "Context":
        clone: Context = Context.__new__(Context)

        clone._phase = self._phase
        clone._recursive = self._recursive
        clone._catalog = self._catalog
        clone._declaration = self._declaration
        clone._query = None if self._query is None else self._query.copy()
        clone._capture = self._capture

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

    # -- the capture ------------------------------------------------------

    @property
    def captured(self) -> str:
        return self._capture

    def capture(self, text: str) -> bool:
        """Set `text` aside for the selector that commits it."""

        self._capture = text

        return True

    def append(self, text: str, separator: str = ", ") -> bool:
        """Add `text` to what is set aside."""

        self._capture = f"{self._capture}{separator}{text}" if self._capture else text

        return True

    # -- definitions ------------------------------------------------------

    @debug.traced(lambda self: "use_recursive()")
    def use_recursive(self) -> bool:
        """Make every definition of the statement one that may read itself."""

        if not self._phase.is_at(Phase.PREAMBLE) or self._catalog.top is not None:
            return False

        self._recursive = True

        return True

    def get_reserved_names(self) -> Exclusion:
        """What a definition's name may not spell: anything the stack defines."""

        return self._catalog.reserved

    def get_column_reserved_names(self) -> Exclusion:
        """What a name in a definition's column list may not spell.

        Anything the stack defines, the definition's own name, and every name
        the list already holds.
        """

        assert self._declaration is not None

        return self._catalog.reserved.including([self._declaration.name], self._declaration.columns)

    @debug.traced(lambda self, name: f"begin_definition({name})")
    def begin_definition(self, name: str) -> bool:
        """Declare the definition `<name>`, whose body comes once it is declared."""

        if not self._catalog.reserved.allows(name) or not self._enter(Phase.DECLARATION):
            return False

        self._declaration = Declaration(name)

        return True

    @debug.traced(lambda self, column: f"name_column({column})")
    def name_column(self, column: str) -> bool:
        """Add `column` to the column list of the definition being declared."""

        if self._declaration is None or not self._phase.is_at(Phase.DECLARATION):
            return False

        if not self.get_column_reserved_names().allows(column):
            return False

        self._declaration = replace(self._declaration, columns=self._declaration.columns + (column,))

        return True

    @debug.traced(lambda self: "open_definition()")
    def open_definition(self) -> bool:
        """Open the body of the definition just declared."""

        if self._declaration is None or not self._enter(Phase.DEFINITION):
            return False

        declaration: Declaration = self._declaration

        self._query = VirtualTable(self._catalog, Frame(declaration.name, declaration.columns))
        self._declaration = None

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

    # -- compounds --------------------------------------------------------

    @debug.traced(lambda self, operator: f"combine({operator})")
    def combine(self, operator: SetOperator) -> bool:
        """End the member being written with `operator`, and open the next one."""

        if self._query is None:
            return False

        member: VirtualTable | None = self._query.combine(operator, self._recursive)

        if member is None:
            return False

        self._query = member

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
        declaration: str = "" if self._declaration is None else f"\nDeclaring        = {self._declaration}"
        recursive: str = " (recursive)" if self._recursive else ""

        return (
            f"Statement        = {self._phase}{recursive}\n"
            f"Stack            = {self._catalog}"
            f"{declaration}{query}"
        )

    def __repr__(self) -> str:
        return f"Context(phase={self.phase.name}, query={self._query!r})"
