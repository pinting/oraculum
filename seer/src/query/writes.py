"""The write half of the virtual table: every operation the grammar records through.

Each one is the same three things: refused outside the clauses it belongs to
(`during`), traced (`debug.traced`), and handed to the part that owns what it
writes - the selection, the sources, the refinement or the presentation. The
rules live in those parts; what is here is only which clause may write what,
so the lifecycle of a query can be read off the decorators alone.

`VirtualTable` is the class these are written for. They are kept apart from
it so that the structure of a query - its parts, its stack, its transitions -
reads without the list of everything that may be written into it.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Callable, TypeVar

from .. import debug
from ..model import Kinds, column_name
from ..resolution import JoinType, Neighbor
from ..state import Clause, Machine
from .expression import Column, Direction, Expr
from .presentation import Presentation
from .refinement import Refinement
from .operand import Operand

if TYPE_CHECKING:
    from .selection import Selection
    from .sources import Sources

F = TypeVar("F", bound=Callable[..., bool])

def during(*clauses: Clause) -> Callable[[F], F]:
    """Refuse an operation outside the clauses it belongs to."""

    def decorate(method: F) -> F:
        @functools.wraps(method)
        def wrapper(self: "Writes", *args, **kwargs) -> bool:
            if not self._clause.is_at(*clauses):
                return False

            return method(self, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorate

class Writes:
    """Every write a query takes, by the clause it belongs to."""

    __slots__ = ()

    # What the virtual table holds, as far as writing it needs.
    if TYPE_CHECKING:
        _clause: Machine[Clause]
        _selection: Selection
        _refinement: Refinement | None
        _presentation: Presentation | None

        @property
        def sources(self) -> Sources: ...

        @property
        def refinement(self) -> Refinement: ...

        @property
        def presentation(self) -> Presentation: ...

    # -- PROJECTION -------------------------------------------------------

    @debug.traced(lambda self: "use_distinct()")
    @during(Clause.PROJECTION)
    def use_distinct(self) -> bool:
        return self._selection.deduplicate()

    @debug.traced(lambda self, qualifier: f"open_qualifier({qualifier})")
    @during(Clause.PROJECTION)
    def open_qualifier(self, qualifier: str) -> bool:
        """Open an alias, consumed by the next column."""

        return self._selection.open(qualifier)

    @debug.traced(
        lambda self, column, kinds=None: f"use_column({column_name(self._selection.qualifier, column)})"
    )
    @during(Clause.PROJECTION)
    def use_column(self, column: str, kinds: Kinds | None = None) -> bool:
        """Demand `column` under the open qualifier, as a value of `kinds`."""

        return self._selection.column(column, kinds)

    @debug.traced(
        lambda self, columns, kinds: f"narrow({', '.join(c.text for c in columns)} to {sorted(map(str, kinds))})"
    )
    @during(Clause.PROJECTION)
    def narrow(self, columns: tuple[Column, ...], kinds: Kinds) -> bool:
        return self._selection.narrow(columns, kinds)

    @debug.traced(lambda self, expr: f"add_item({expr})")
    @during(Clause.PROJECTION)
    def add_item(self, expr: Expr) -> bool:
        return self._selection.add(expr)

    @debug.traced(lambda self, alias: f"name_item({alias})")
    @during(Clause.PROJECTION)
    def name_item(self, alias: str) -> bool:
        """Give the item just written an output name."""

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

    @debug.traced(lambda self, key: f"use_group_key({key})")
    @during(Clause.GROUPING)
    def use_group_key(self, key: Operand) -> bool:
        grouped: Refinement | None = self.refinement.group(key)

        if grouped is None:
            return False

        self._refinement = grouped

        return True

    # -- ORDERING, LIMITING -----------------------------------------------

    @debug.traced(lambda self, key: f"use_order_key({key})")
    @during(Clause.ORDERING)
    def use_order_key(self, key: Operand) -> bool:
        return self._present_with(self.presentation.sort(key))

    @debug.traced(lambda self, direction: f"use_order_direction({direction})")
    @during(Clause.ORDERING)
    def use_order_direction(self, direction: Direction) -> bool:
        return self._present_with(self.presentation.direct(direction))

    @debug.traced(lambda self, count: f"use_limit({count})")
    @during(Clause.LIMITING)
    def use_limit(self, count: str) -> bool:
        return self._present_with(self.presentation.limited(count))

    @debug.traced(lambda self, count: f"use_offset({count})")
    @during(Clause.LIMITING)
    def use_offset(self, count: str) -> bool:
        return self._present_with(self.presentation.offset_by(count))

    def _present_with(self, presentation: Presentation | None) -> bool:
        if presentation is None:
            return False

        self._presentation = presentation

        return True
