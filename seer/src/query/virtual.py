"""The virtual table: the data structure of one SELECT, as it is written.

Everything a query commits to lives here and nowhere else - the items it
projects, the tables those items demand, the FROM nodes that supply them, the
relation those nodes produce, the values it groups on, the conditions it
writes and the order it presents its result in. It is held in one part per
stretch of the lifecycle:

    Selection      PROJECTION  the items, and what they demand     (selection.py)
    Sources        SOURCE      the FROM clause being placed        (sources.py)
    Refinement     the body    WHERE, GROUP BY, HAVING             (refinement.py)
    Presentation   after it    ORDER BY, LIMIT                     (presentation.py)

and this class is what binds them to the clause machine of `state.clause`:

* which operation a clause allows is declared with `during`, so a mutation
  outside its clause is refused rather than half applied;
* what a transition builds is the two hooks `_on_enter` and `_on_exit`;
* which transitions the query may take is `can_enter`, which asks the rules
  that span parts (`lifecycle.py`) - the projection complete before FROM, the
  body complete before anything after it.

The grammar reads through the parts (`query.selection.columns()`) and writes
through this class (`query.use_column(...)`), so every write is checked
against the lifecycle and traced.

A query also sits on a stack. It is written over a `Catalog` - the schema
plus every virtual table closed before it - and a query that is named, a
`WITH` definition, is itself pushed onto that stack once it closes, exporting
the table its result produced (`derivation.py`). Every lookup a query does
goes through its catalog, so it sees itself and everything stacked below it,
and nothing above.

Where the query stands - main query, definition, later member of a compound,
recursive member - is its `Frame`, and the frame is what decides the rules the
parts are built with. A compound is written member by member: `combine` closes
this member and answers with the next, which holds every member before it.

Every query is a value as far as the graph can tell: a selector copies it,
modifies the copy and hands it on, so branches never see each other. The parts
that are immutable once built are shared by every copy, and a closed query is
immutable outright, which is what lets the stack be shared too.
"""

from __future__ import annotations

from typing import Iterator

from .. import debug
from ..model import Schema, Table
from ..resolution import JoinType
from ..state import BODY, PRESENTATION, Clause, Machine, clause_machine
from .catalog import Catalog
from .compound import SetOperator
from .derivation import Result, merge, result, table
from .frame import Frame
from .lifecycle import may_enter
from .names import Exclusion
from .presentation import Presentation, can_sort
from .refinement import Refinement
from .relation import Relation
from .selection import Selection
from .sources import Sources
from .writes import Writes

class VirtualTable(Writes):
    __slots__ = (
        "_catalog",
        "_frame",
        "_clause",
        "_selection",
        "_sources",
        "_refinement",
        "_presentation",
        "_result",
    )

    def __init__(self, catalog: Catalog | None = None, frame: Frame = Frame()) -> None:
        """A query over `catalog`, standing where `frame` says."""

        if catalog is None:
            return

        # A definition's own name is reserved inside it too: it is not a
        # table there yet, and nothing should look as if it were.
        reserved: Exclusion = catalog.reserved

        if frame.name is not None:
            reserved = reserved.including([frame.name])

        self._catalog = catalog
        self._frame = frame
        self._clause: Machine[Clause] = clause_machine()
        self._selection: Selection = Selection(
            catalog.schema, reserved, frame.contract(catalog.provisional)
        )
        self._sources: Sources | None = None
        self._refinement: Refinement | None = None
        self._presentation: Presentation | None = None
        self._result: Result | None = None

    def copy(self) -> "VirtualTable":
        clone: VirtualTable = VirtualTable.__new__(VirtualTable)

        clone._catalog = self._catalog
        clone._frame = self._frame
        clone._clause = self._clause
        clone._selection = self._selection.copy()
        clone._sources = None if self._sources is None else self._sources.copy(clone._selection)
        clone._refinement = self._refinement
        clone._presentation = self._presentation
        clone._result = self._result

        return clone

    # -- the stack --------------------------------------------------------

    @property
    def catalog(self) -> Catalog:
        """The stack this query is written over."""

        return self._catalog

    @property
    def frame(self) -> Frame:
        return self._frame

    @property
    def name(self) -> str | None:
        """What the query exports as; `None` for the main query."""

        return self._frame.name

    @property
    def below(self) -> "VirtualTable | None":
        """The virtual table stacked right under this one."""

        return self._catalog.top

    def stack(self) -> Iterator["VirtualTable"]:
        """This query and every one below it, the most recent first."""

        yield self
        yield from self._catalog.layers()

    def is_derived(self) -> bool:
        return self._frame.is_derived

    def is_closed(self) -> bool:
        return self._clause.is_at(Clause.CLOSED)

    def own_result(self) -> Result:
        """What this member alone produces, once its body is complete."""

        assert self._result is not None, "a query has no result before its body is complete"

        return self._result

    def result(self) -> Result:
        """What the query produces: this member's result, merged with the members before it."""

        if self._frame.compound is None:
            return self.own_result()

        return merge([member.own_result() for member in self._frame.compound.members] + [self.own_result()])

    def export(self) -> Table:
        """The table a closed definition contributes to the stack."""

        assert self.is_closed() and self.is_derived(), "only a closed definition exports a table"

        return table(self.result(), self._frame.names())

    # -- the parts --------------------------------------------------------

    @property
    def schema(self) -> Schema:
        """Every table the query can read: the physical ones and the stack's."""

        return self._catalog.schema

    @property
    def clause(self) -> Clause:
        return self._clause.state

    @property
    def selection(self) -> Selection:
        return self._selection

    @property
    def sources(self) -> Sources:
        """The FROM clause; only there once the `FROM` keyword has been taken."""

        assert self._sources is not None, "no FROM clause before SOURCE"

        return self._sources

    @property
    def refinement(self) -> Refinement:
        """What is written against the closed relation; only there after SOURCE."""

        assert self._refinement is not None, "no closed relation before SOURCE is left"

        return self._refinement

    @property
    def presentation(self) -> Presentation:
        """ORDER BY and LIMIT; only there once the body is left."""

        assert self._presentation is not None, "no presentation before the body is complete"

        return self._presentation

    # -- the clause machine -----------------------------------------------

    def _advance(self, target: Clause) -> bool:
        if not self.can_enter(target):
            return False

        advanced: Machine[Clause] | None = self._clause.advance(target)

        if advanced is None:
            return False

        if advanced is not self._clause:
            leaving: Clause = self._clause.state

            self._clause = advanced

            self._on_exit(leaving)
            self._on_enter(target)

        return True

    def _on_enter(self, clause: Clause) -> None:
        # The join graph is built over whatever the projection ended up
        # requiring, which is only final once the projection is over.
        if clause is Clause.SOURCE:
            self._sources = self._open_sources()

        # The result is fixed the moment the body is left, and computed once
        # here rather than by every clause, member or query that reads it.
        if clause in PRESENTATION and self._result is None:
            self._result = result(self._selection.projection, self.refinement.relation)

        if clause in (Clause.ORDERING, Clause.LIMITING) and self._presentation is None:
            self._presentation = self._present()

    def _on_exit(self, clause: Clause) -> None:
        # Whatever follows the FROM clause reads the relation it produced, and
        # it is only final once nothing more can be placed.
        if clause is Clause.SOURCE:
            self._refinement = Refinement(
                Relation(self.schema, self.sources.nodes(), self.sources.nullable())
            )

    def _open_sources(self) -> Sources:
        # A recursive member joins only by inner joins: an outer join could
        # pad the recursion with rows it never produced.
        if self._frame.recursive:
            return Sources(self.schema, self._selection, (JoinType.INNER,))

        return Sources(self.schema, self._selection)

    def _present(self) -> Presentation:
        if self._frame.compound is not None:
            return Presentation.of_compound(self.result())

        return Presentation.of_query(self._selection.projection, self.own_result(), self.refinement)

    def can_enter(self, clause: Clause) -> bool:
        """Whether the query may move to `clause` from where it stands; see `lifecycle.py`."""

        return may_enter(
            clause, self._clause, self._frame, self._selection, self._sources, self._refinement
        )

    def can_order(self) -> bool:
        """Whether an ORDER BY may be written here, with something to sort by."""

        compound: Result | None = None if self._frame.compound is None else self._frame.compound.result()

        return self.can_enter(Clause.ORDERING) and can_sort(self._selection.projection, compound)

    @debug.traced(lambda self: "enter_source()")
    def enter_source(self) -> bool:
        return self._advance(Clause.SOURCE)

    @debug.traced(lambda self: "enter_filter()")
    def enter_filter(self) -> bool:
        return self._advance(Clause.FILTER)

    @debug.traced(lambda self: "enter_grouping()")
    def enter_grouping(self) -> bool:
        return self._advance(Clause.GROUPING)

    @debug.traced(lambda self: "enter_having()")
    def enter_having(self) -> bool:
        return self._advance(Clause.HAVING)

    @debug.traced(lambda self: "enter_ordering()")
    def enter_ordering(self) -> bool:
        return self._advance(Clause.ORDERING)

    @debug.traced(lambda self: "enter_limiting()")
    def enter_limiting(self) -> bool:
        return self._advance(Clause.LIMITING)

    @debug.traced(lambda self: "close()")
    def close(self) -> bool:
        return self._advance(Clause.CLOSED)

    def can_close(self) -> bool:
        return not self.is_closed() and self.can_enter(Clause.CLOSED)

    # -- compounds --------------------------------------------------------

    def can_combine(self) -> bool:
        """Whether a set operator may end this member and start another.

        Only the body may be combined - ORDER BY and LIMIT belong to the
        compound, after its last member - and a member that read its own
        definition is the recursive one, which has to be the last.
        """

        if not self._clause.is_at(*BODY) or not self.can_close():
            return False

        provisional: str | None = self._catalog.provisional

        return not (self._frame.recursive and provisional is not None and self.sources.places(provisional))

    @debug.traced(lambda self, operator, recursive=False: f"combine({operator})")
    def combine(self, operator: SetOperator, recursive: bool = False) -> "VirtualTable | None":
        """Close this member and open the next, which `operator` joins to it.

        Where the next member may read the definition (`Frame.after`), it does
        so as the members so far export it.
        """

        if not self.can_combine() or not self.close():
            return None

        frame: Frame = self._frame.after(self, operator, recursive)
        catalog: Catalog = self._catalog.base

        if frame.recursive:
            assert frame.name is not None and frame.compound is not None

            catalog = catalog.reading(frame.name, table(frame.compound.result(), frame.names()))

        return VirtualTable(catalog, frame)

    # -- debug ------------------------------------------------------------

    def __str__(self) -> str:
        """The state block `debug.py` prints after every modifying operation."""

        compound: str = "" if self._frame.compound is None else f"\nCompound         = {self._frame.compound}"
        sources: str = "" if self._sources is None else str(self._sources)
        refinement: str = "" if self._refinement is None else f"\n{self._refinement}"
        presentation: str = "" if self._presentation is None else f"\n{self._presentation}"

        return (
            f"Query            = {' -> '.join(layer.name or '(main)' for layer in self.stack())}"
            f"{compound}\n"
            f"Clause           = {self._clause}\n"
            f"{self._selection}\n"
            f"Used references  = {sources}"
            f"{refinement}"
            f"{presentation}"
        )

    def __repr__(self) -> str:
        return (
            f"VirtualTable(name={self.name!r}, clause={self.clause.name}, "
            f"items={self._selection.projection})"
        )
