"""The virtual table: the data structure of one SELECT, as it is written.

Everything a query commits to lives here and nowhere else - the items it
projects, the tables those items demand, the FROM nodes that supply them, the
relation those nodes produce, the columns it groups on and the conditions it
writes. It is held in one part per stretch of the lifecycle:

    Selection      PROJECTION  the items, and what they demand  (selection.py)
    Sources        SOURCE      the FROM clause being placed     (sources.py)
    Refinement     after it    WHERE, GROUP BY, HAVING          (refinement.py)

and this class is what binds them to the clause machine of `state.clause`:

* which operation a clause allows is declared with `during`, so a mutation
  outside its clause is refused rather than half applied;
* what a transition builds is the two hooks `_on_enter` and `_on_exit`;
* the rules that span parts - when the query may end - are `can_close`.

The grammar reads through the parts (`query.selection.columns()`) and writes
through this class (`query.use_column(...)`), so every write is checked
against the lifecycle and traced.

A query also sits on a stack. It is written over a `Catalog` - the schema
plus every virtual table closed before it - and a query that is named, a
`WITH` definition, is itself pushed onto that stack once it closes, exporting
the table its projection produced (`derivation.py`). Every lookup a query does
goes through its catalog, so it sees itself and everything stacked below it,
and nothing above.

Every query is a value as far as the graph can tell: a selector copies it,
modifies the copy and hands it on, so branches never see each other. The parts
that are immutable once built are shared by every copy, and a closed query is
immutable outright, which is what lets the stack be shared too.
"""

from __future__ import annotations

import functools
from typing import Callable, Iterator, TypeVar

from .. import debug
from ..model import Function, Schema, Table, column_name
from ..resolution import JoinType, Neighbor
from ..state import Clause, Machine, clause_machine
from .catalog import Catalog
from .derivation import derive
from .names import Exclusion
from .refinement import Refinement
from .relation import Relation
from .selection import Selection
from .sources import Sources

F = TypeVar("F", bound=Callable[..., bool])

def during(*clauses: Clause) -> Callable[[F], F]:
    """Refuse an operation outside the clauses it belongs to."""

    def decorate(method: F) -> F:
        @functools.wraps(method)
        def wrapper(self: "VirtualTable", *args, **kwargs) -> bool:
            if not self._clause.is_at(*clauses):
                return False

            return method(self, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorate

class VirtualTable:
    __slots__ = (
        "_catalog",
        "_name",
        "_clause",
        "_selection",
        "_sources",
        "_refinement",
        "_export",
    )

    def __init__(self, catalog: Catalog | None = None, name: str | None = None) -> None:
        """A query over `catalog`, exported as `name` once closed if it has one."""

        if catalog is None:
            return

        # A definition's own name is reserved inside it too: it is not a
        # table there yet, and nothing should look as if it were.
        reserved: Exclusion = catalog.reserved if name is None else catalog.reserved.including([name])

        self._catalog = catalog
        self._name = name
        self._clause: Machine[Clause] = clause_machine()
        self._selection: Selection = Selection(catalog.schema, reserved, derived=name is not None)
        self._sources: Sources | None = None
        self._refinement: Refinement | None = None
        self._export: Table | None = None

    def copy(self) -> "VirtualTable":
        clone: VirtualTable = VirtualTable.__new__(VirtualTable)

        clone._catalog = self._catalog
        clone._name = self._name
        clone._clause = self._clause
        clone._selection = self._selection.copy()
        clone._sources = None if self._sources is None else self._sources.copy(clone._selection)
        clone._refinement = self._refinement
        clone._export = self._export

        return clone

    # -- the stack --------------------------------------------------------

    @property
    def catalog(self) -> Catalog:
        """The stack this query is written over."""

        return self._catalog

    @property
    def name(self) -> str | None:
        """What the query exports as; `None` for the main query."""

        return self._name

    @property
    def below(self) -> "VirtualTable | None":
        """The virtual table stacked right under this one."""

        return self._catalog.top

    def stack(self) -> Iterator["VirtualTable"]:
        """This query and every one below it, the most recent first."""

        yield self
        yield from self._catalog.layers()

    def is_derived(self) -> bool:
        return self._name is not None

    def is_closed(self) -> bool:
        return self._clause.is_at(Clause.CLOSED)

    def export(self) -> Table:
        """The table a closed definition contributes to the stack."""

        assert self._export is not None, "only a closed definition exports a table"

        return self._export

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

    # -- the clause machine -----------------------------------------------

    def _advance(self, target: Clause) -> bool:
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
            self._sources = Sources(self.schema, self._selection)

        # What a definition exports is fixed the moment it closes, and it is
        # computed once here rather than by every query stacked over it.
        if clause is Clause.CLOSED and self.is_derived():
            self._export = derive(self._selection.projection, self.refinement.relation)

    def _on_exit(self, clause: Clause) -> None:
        # Whatever follows the FROM clause reads the relation it produced, and
        # it is only final once nothing more can be placed.
        if clause is Clause.SOURCE:
            self._refinement = Refinement(Relation(self.schema, self.sources.nodes()))

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

    @debug.traced(lambda self: "close()")
    def close(self) -> bool:
        return self.can_close() and self._advance(Clause.CLOSED)

    def can_close(self) -> bool:
        """Whether the query may end here.

        Its FROM clause has to supply everything the projection asked for; a
        projection that mixes plain columns with aggregates has to be grouped;
        and a grouped one has to group every plain column it keeps.
        """

        if self._clause.is_at(Clause.CLOSED) or not self._clause.can_advance(Clause.CLOSED):
            return False

        if self._sources is None or not self._sources.nodes() or not self._sources.is_satisfied():
            return False

        grouped: bool = self._refinement is not None and bool(self._refinement.grouping)

        if not grouped:
            return not self._selection.projection.is_mixed()

        return self.refinement.covers(self._selection.projection)

    # -- PROJECTION -------------------------------------------------------

    @debug.traced(lambda self, qualifier: f"open_qualifier({qualifier})")
    @during(Clause.PROJECTION)
    def open_qualifier(self, qualifier: str) -> bool:
        """Open an alias, consumed by the next column."""

        return self._selection.open(qualifier)

    @debug.traced(lambda self, column: f"use_column({column_name(self._selection.qualifier, column)})")
    @during(Clause.PROJECTION)
    def use_column(self, column: str) -> bool:
        return self._selection.column(column)

    @debug.traced(lambda self, function, column: f"use_aggregate({function.spell(column)})")
    @during(Clause.PROJECTION)
    def use_aggregate(self, function: Function, column: str | None) -> bool:
        """Apply `function` to `column`, or to `*` where `column` is `None`."""

        return self._selection.aggregate(function, column)

    @debug.traced(lambda self, alias: f"name_item({alias})")
    @during(Clause.PROJECTION)
    def name_item(self, alias: str) -> bool:
        """Give the aggregate just written an output name."""

        return self._selection.name(alias)

    # -- SOURCE -----------------------------------------------------------

    @debug.traced(lambda self, node: f"use_table({node})")
    @during(Clause.SOURCE)
    def use_table(self, node: str) -> bool:
        return self.sources.place(node)

    @debug.traced(
        lambda self, neighbor, join_type=JoinType.INNER: f"join_table({neighbor.format(join_type)})"
    )
    @during(Clause.SOURCE)
    def join_table(self, neighbor: Neighbor, join_type: JoinType = JoinType.INNER) -> bool:
        return self.sources.join(neighbor, join_type)

    # -- FILTER, GROUPING, HAVING -----------------------------------------

    @debug.traced(lambda self, text: f"use_filter({text})")
    @during(Clause.FILTER, Clause.HAVING)
    def use_filter(self, text: str) -> bool:
        """Record a condition of the clause that is open, once written whole."""

        if not text:
            return False

        if self._clause.is_at(Clause.FILTER):
            self._refinement = self.refinement.filter(text)
        else:
            self._refinement = self.refinement.having_filter(text)

        return True

    @debug.traced(lambda self, text: f"use_group_key({text})")
    @during(Clause.GROUPING)
    def use_group_key(self, text: str) -> bool:
        grouped: Refinement | None = self.refinement.group(text)

        if grouped is None:
            return False

        self._refinement = grouped

        return True

    # -- debug ------------------------------------------------------------

    def __str__(self) -> str:
        """The state block `debug.py` prints after every modifying operation."""

        sources: str = "" if self._sources is None else str(self._sources)
        refinement: str = (
            "" if self._refinement is None else f"\n{self._refinement}"
        )

        return (
            f"Query            = {' -> '.join(layer.name or '(main)' for layer in self.stack())}\n"
            f"Clause           = {self._clause}\n"
            f"{self._selection}\n"
            f"Used references  = {sources}"
            f"{refinement}"
        )

    def __repr__(self) -> str:
        return (
            f"VirtualTable(name={self._name!r}, clause={self.clause.name}, "
            f"items={self._selection.projection})"
        )
