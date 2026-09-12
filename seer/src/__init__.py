"""seer - an SQL syntax graph generator framework built on the `kernel` library.

seer owns the modelling and the syntax graph; `kernel` owns the indexes, the
active heads walking them and the worker pool that drives them. The split runs
through `engine.py`: the kernel notifies seer when a head reaches the end of
its index, and seer answers with the indexes that may follow.

    factory.py        drafts in, kernel index ids out
    engine.py         the syntax graph and the kernel's resolver
    graph.py          the SQL SELECT language
    context.py        the generation state a node is resolved against

The modelling underneath the graph is a stack of its own:

    schema.py         the SQL schema, parsed with sqlglot
    root.py           unqualified field resolution over GF(2)
    scope.py          one alias, narrowed by set intersection
    scopes.py         the registry of alias scopes
    conflicts.py      root and scopes behind one interface
    relationships.py  the foreign key join graph

This module re-exports the public surface; `main.py` and `core.py` import from
here.
"""

from __future__ import annotations

from . import debug
from .conflicts import Conflicts
from .context import Context, GLOBAL_NAMESPACE
from .engine import Engine, Head, Node, Selector, Thunk, ThunkFn
from .factory import DraftKind, IndexDraft, IndexFactory, IndexSpec
from .graph import alias, root
from .relationships import (
    JOIN_TYPES,
    EdgeLabel,
    FieldRef,
    JoinGraph,
    JoinType,
    Neighbor,
    Relationships,
)
from .root import Root
from .schema import RESERVED, Field, Reference, Schema, Table, Type, parse_schema
from .scope import Scope
from .scopes import Scopes, qualify, sql_name, unqualify

__all__ = [
    "Conflicts",
    "Context",
    "debug",
    "DraftKind",
    "EdgeLabel",
    "Engine",
    "Field",
    "FieldRef",
    "GLOBAL_NAMESPACE",
    "Head",
    "IndexDraft",
    "IndexFactory",
    "IndexSpec",
    "JOIN_TYPES",
    "JoinGraph",
    "JoinType",
    "Neighbor",
    "Node",
    "RESERVED",
    "Reference",
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
    "alias",
    "parse_schema",
    "qualify",
    "root",
    "sql_name",
    "unqualify",
]
