"""Forward resolution: from what the projection names to what FROM must supply.

    columns.py        which tables carry each column name, shared by both resolvers
    root.py           unqualified fields, as a polynomial over GF(2)
    scope.py          one alias, narrowed by set intersection
    scopes.py         the registry of alias scopes
    conflicts.py      root and scopes behind one interface
    joins.py          the edges of the join graph, following keys through lineage
    relationships.py  the walk the FROM clause takes over that graph
"""

from .columns import ColumnIndex, Kinds
from .conflicts import Conflicts
from .joins import JOIN_TYPES, EdgeLabel, FieldRef, JoinType, Neighbor
from .relationships import Relationships
from .root import Root
from .scope import Scope
from .scopes import Scopes

__all__ = [
    "ColumnIndex",
    "Conflicts",
    "EdgeLabel",
    "FieldRef",
    "JOIN_TYPES",
    "JoinType",
    "Kinds",
    "Neighbor",
    "Relationships",
    "Root",
    "Scope",
    "Scopes",
]
