"""seer - an SQL syntax graph generator framework built on the `kernel` library.

seer owns the modelling and the syntax graph; `kernel` owns the indexes, the
active heads walking them and the worker pool that drives them. The split runs
through `runtime/engine.py`: the kernel notifies seer when a head reaches the
end of its index, and seer answers with the indexes that may follow.

    runtime/          the kernel boundary: drafts, thunks, the engine
    model/            the schema, names, type classes and operators
    resolution/       projection -> required tables -> join graph
    query/            the virtual table: the data structure of a query, and its stack
    state/            the state machines, apart from the work they trigger
    context.py        the generation state a node is resolved against
    grammar/          the SQL SELECT language, clause by clause
    debug.py          state tracing

This module re-exports the public surface; `main.py`, `core.py` and `test.py`
import from here.
"""

from __future__ import annotations

from . import debug
from .context import Context
from .grammar import root
from .model import (
    BINARY_OPERATORS,
    FUNCTIONS,
    KEYWORDS,
    LITERALS,
    Field,
    Function,
    Operator,
    Reference,
    Schema,
    Table,
    Type,
    TypeClass,
    classify,
    is_comparable,
    literal_for,
    operators_for,
    parse_schema,
    qualify,
    reference_name,
    sql_name,
    unqualify,
)
from .query import (
    Catalog,
    Exclusion,
    Grouping,
    Item,
    NameUse,
    Operand,
    Projection,
    Refinement,
    Relation,
    Selection,
    Sources,
    VirtualTable,
    derive,
)
from .resolution import (
    JOIN_TYPES,
    ColumnIndex,
    Conflicts,
    EdgeLabel,
    FieldRef,
    JoinType,
    Neighbor,
    Relationships,
    Root,
    Scope,
    Scopes,
)
from .runtime import (
    DraftKind,
    Engine,
    Head,
    IndexDraft,
    IndexFactory,
    IndexSpec,
    JoinGraph,
    Node,
    Selector,
    Thunk,
    ThunkFn,
)
from .state import Clause, Machine, Phase

__all__ = [
    "BINARY_OPERATORS",
    "Catalog",
    "Clause",
    "ColumnIndex",
    "Conflicts",
    "Context",
    "debug",
    "DraftKind",
    "EdgeLabel",
    "Engine",
    "Exclusion",
    "Field",
    "FieldRef",
    "FUNCTIONS",
    "Function",
    "Grouping",
    "Item",
    "NameUse",
    "Projection",
    "Sources",
    "VirtualTable",
    "Head",
    "IndexDraft",
    "IndexFactory",
    "IndexSpec",
    "JOIN_TYPES",
    "JoinGraph",
    "JoinType",
    "KEYWORDS",
    "LITERALS",
    "Machine",
    "Neighbor",
    "Node",
    "Operand",
    "Operator",
    "Phase",
    "Reference",
    "Refinement",
    "Relation",
    "Selection",
    "Relationships",
    "Root",
    "Schema",
    "Scope",
    "Scopes",
    "Selector",
    "Table",
    "Thunk",
    "ThunkFn",
    "Type",
    "TypeClass",
    "classify",
    "derive",
    "is_comparable",
    "literal_for",
    "operators_for",
    "parse_schema",
    "qualify",
    "reference_name",
    "root",
    "sql_name",
    "unqualify",
]
