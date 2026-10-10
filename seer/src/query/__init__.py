"""The virtual table: the data structure of the query being written.

    projection.py     the items selected, and the qualifier one has opened
    selection.py      PROJECTION: the projection and what it demands of the tables
    sources.py        SOURCE: the FROM clause, placed against the selection
    relation.py       the columns a closed FROM clause offers, and their spellings
    grouping.py       the grouped columns, and what they cover
    refinement.py     after SOURCE: WHERE, GROUP BY and HAVING over the relation
    names.py          what an invented name may not spell
    derivation.py     the table a closed definition exports
    catalog.py        the stack of virtual tables a query is written over
    virtual.py        the virtual table: the parts, bound to the clause machine
"""

from .catalog import Catalog
from .derivation import derive
from .grouping import Grouping
from .names import Exclusion, NameUse
from .projection import Item, Projection
from .refinement import Refinement
from .relation import Operand, Relation
from .selection import Selection
from .sources import Sources
from .virtual import VirtualTable

__all__ = [
    "Catalog",
    "Exclusion",
    "Grouping",
    "Item",
    "NameUse",
    "Operand",
    "Projection",
    "Refinement",
    "Relation",
    "Selection",
    "Sources",
    "VirtualTable",
    "derive",
]
