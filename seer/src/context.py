"""Generation state shared by the nodes of the syntax graph.

A context owns a `Conflicts` and a `Relationships`, and tracks the query
through the two phases a SELECT is resolved in:

1. **fields** - `Conflicts` narrows the table space as fields are selected,
   qualified by an alias or not.
2. **FROM / JOIN** - `Relationships` walks the foreign key graph to connect
   the tables `Conflicts` ended up requiring.
3. **WHERE** - `Relation` holds the virtual table the finished clause produced,
   and the conditions are gated on the types of its columns.

Each boundary falls on a token. `enter_from()` is what the selector on the
`FROM` keyword calls, and it is where the join graph is built, because only
then is the required table set final; `enter_where()` is the same move one
phase later, on the `WHERE` keyword, because only then is the FROM clause
final. The second boundary only ever reads: a filter can neither require a
table nor satisfy one.

Everything a thunk asks is ordered and side effect free, and everything a
selector applies happens on a `copy()`, so branches never see each other.

Every operation that modifies a context traces the whole resolver state. See
`debug.py`; tracing is off until a driver enables it.
"""

from __future__ import annotations

from . import debug
from .conflicts import Conflicts
from .operators import TypeClass
from .relation import Operand, Relation
from .relationships import JoinType, Neighbor, Relationships
from .schema import RESERVED, Schema
from .scopes import unqualify

GLOBAL_NAMESPACE: str = ""

def _qualified(context: "Context", field: str) -> str:
    """`alias.field` when a namespace is open, otherwise just `field`."""

    namespace: str = context.get_current_namespace()

    return f"{namespace}.{field}" if namespace else field

class Context:
    __slots__ = (
        "_schema",
        "_conflicts",
        "_relationships",
        "_relation",
        "_current_namespace",
        "_reserved",
    )

    def __init__(self, schema: Schema | None = None) -> None:
        if schema is None:
            return

        self._schema = schema
        self._conflicts = Conflicts(schema)
        self._relationships: Relationships | None = None
        self._relation: Relation | None = None
        self._current_namespace: str = GLOBAL_NAMESPACE
        self._reserved: tuple[str, ...] | None = None

    def copy(self) -> "Context":
        clone: Context = Context.__new__(Context)

        clone._schema = self._schema
        clone._conflicts = self._conflicts.copy()
        clone._relationships = (
            None if self._relationships is None else self._relationships.copy()
        )
        clone._relation = None if self._relation is None else self._relation.copy()
        clone._current_namespace = self._current_namespace
        clone._reserved = self._reserved

        return clone

    @property
    def schema(self) -> Schema:
        return self._schema

    @property
    def conflicts(self) -> Conflicts:
        return self._conflicts

    @property
    def relationships(self) -> Relationships | None:
        return self._relationships

    @property
    def relation(self) -> Relation | None:
        return self._relation

    # -- field phase ------------------------------------------------------

    @debug.traced(lambda self, namespace: f"set_current_namespace({namespace})")
    def set_current_namespace(self, namespace: str) -> None:
        """Open an alias, consumed by the next `use_field`."""

        self._current_namespace = namespace

    def get_current_namespace(self) -> str:
        return self._current_namespace

    def get_fields(self) -> list[str]:
        """Fields selectable right now, sorted so expansion is reproducible."""

        return sorted(self._conflicts.get_fields(self._current_namespace))

    def get_excluded_fields(self) -> list[str]:
        return sorted(self._conflicts.get_excluded_fields(self._current_namespace))

    @debug.traced(lambda self, field: f"use_field({_qualified(self, field)})")
    def use_field(self, field: str) -> bool:
        namespace: str = self._current_namespace

        self._current_namespace = GLOBAL_NAMESPACE

        return self._conflicts.use_field(namespace, field)

    def get_namespaces(self) -> list[str]:
        return self._conflicts.scopes.names()

    def get_reserved_names(self) -> tuple[str, ...]:
        """Names an alias may not spell.

        The SQL keywords of `schema.RESERVED` in both cases, plus every table
        and column name of the schema. An alias that spelled one of those would
        be ambiguous with the token it shadows - `SELECT users.email` would
        open an alias called `users` rather than reference the table - so
        `graph.alias` subtracts them from the identifier pattern.

        Constant for a schema, so it is computed once and carried by `copy()`
        rather than rebuilt per branch.
        """

        if self._reserved is None:
            names: set[str] = {word for word in RESERVED}

            names.update(word.lower() for word in RESERVED)
            names.update(self._schema.get_names())

            self._reserved = tuple(sorted(names))

        return self._reserved

    # -- phase boundary ---------------------------------------------------

    @debug.traced(lambda self: "enter_from()")
    def enter_from(self) -> None:
        """Build the join graph over whatever `Conflicts` ended up requiring.

        Called by the selector on the `FROM` keyword. Idempotent, because a
        branch may reach it more than once while the engine expands.
        """

        self._enter_from()

    def _enter_from(self) -> None:
        if self._relationships is not None:
            return

        self._relationships = Relationships(
            self._schema,
            self._conflicts.get_required_tables(),
        )

    # -- FROM / JOIN phase ------------------------------------------------

    def get_required_tables(self) -> list[str]:
        """Nodes the FROM clause still has to supply, as `"table"` or `"table alias"`."""

        return sorted(self._conflicts.get_required_tables())

    def get_excluded_tables(self) -> list[str]:
        return sorted(self._conflicts.get_excluded_tables())

    @debug.traced(lambda self, node: f"use_table({node})")
    def use_table(self, node: str) -> bool:
        """Open a FROM entry at `node` and satisfy it.

        Mirrors `Relationships.use_table`, which refuses a node that is not
        required, then delegates to `Conflicts`.
        """

        self._enter_from()

        assert self._relationships is not None

        if node not in self._conflicts.get_required_tables():
            return False

        if not self._conflicts.use_table(node):
            return False

        return self._relationships.use_table(node)

    def get_joinable_neighbors(self) -> tuple[Neighbor, ...]:
        """Tables reachable from the current FROM entry by a foreign key."""

        if self._relationships is None:
            return ()

        return self._relationships.get_joinable_neighbors(
            self._conflicts.get_excluded_tables()
        )

    @debug.traced(
        lambda self, neighbor, join_type=JoinType.INNER: f"join_table({neighbor.format(join_type)})"
    )
    def join_table(self, neighbor: Neighbor, join_type: JoinType = JoinType.INNER) -> bool:
        """Join `neighbor` into the current entry, satisfying it if required."""

        if self._relationships is None:
            return False

        if neighbor not in self.get_joinable_neighbors():
            return False

        if neighbor.table in self._conflicts.get_required_tables():
            self._conflicts.use_table(neighbor.table)

        return self._relationships.join_table(neighbor, join_type)

    def get_head(self) -> str | None:
        if self._relationships is None:
            return None

        return self._relationships.head

    def get_used_nodes(self) -> tuple[str, ...]:
        """The nodes the FROM clause has placed, in the order it placed them."""

        if self._relationships is None:
            return ()

        return self._relationships.get_used_nodes()

    # -- second phase boundary --------------------------------------------

    @debug.traced(lambda self: "enter_where()")
    def enter_where(self) -> None:
        """Fix the virtual table over the FROM clause as it now stands.

        Called by the selector on the `WHERE` keyword. Idempotent for the same
        reason `enter_from` is: a branch may reach it more than once while the
        engine expands.
        """

        self._enter_where()

    def _enter_where(self) -> None:
        if self._relation is not None or self._relationships is None:
            return

        self._relation = Relation(self._schema, self._relationships.get_used_nodes())

    # -- WHERE phase ------------------------------------------------------

    def get_operands(self, kind: TypeClass | None = None) -> tuple[Operand, ...]:
        """Columns a condition may name, optionally only those of one class.

        Empty until the `WHERE` keyword has been taken, because until then
        there is no closed FROM clause to read them off.
        """

        if self._relation is None:
            return ()

        return self._relation.get_operands(kind)

    @debug.traced(lambda self, text: f"use_filter({text})")
    def use_filter(self, text: str) -> bool:
        """Record a condition, once it has been written whole."""

        if self._relation is None:
            return False

        return self._relation.use_filter(text)

    def get_used_filters(self) -> tuple[str, ...]:
        if self._relation is None:
            return ()

        return self._relation.get_used_filters()

    # -- completion -------------------------------------------------------

    def is_satisfied(self) -> bool:
        return self._conflicts.is_satisfied()

    def __str__(self) -> str:
        """The state block `debug.py` prints after every modifying operation.

        `Conflicts.__str__` supplies the first six lines; then the FROM clause
        as `Relationships` has it so far, empty until phase two begins, and the
        conditions `Relation` has taken, empty until phase three does.
        """

        references: str = "" if self._relationships is None else str(self._relationships)
        filters: str = "" if self._relation is None else str(self._relation)

        return (
            f"{self._conflicts}\n"
            f"Used references  = {references}\n"
            f"Used filters     = {filters}"
        )

    def __repr__(self) -> str:
        return f"Context(required={self.get_required_tables()})"
