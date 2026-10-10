"""The virtual table: the data structure of the query being written.

    expression.py     the values an item is written as, as a tree
    projection.py     the items selected, and the qualifier one has opened
    shape.py          what a projection has to produce, where its frame decides
    contract.py       what a projection owes its frame: names, a shape, simplicity
    selection.py      PROJECTION: the projection and what it demands of the tables
    placement.py      whether a FROM clause can still be written beside the aliases
    sources.py        SOURCE: the FROM clause, placed against the selection
    operand.py        a value of the closed relation, and the key its spellings share
    relation.py       the values a closed FROM clause offers, and their spellings
    grouping.py       the grouped values, and what they cover
    refinement.py     the body after SOURCE: WHERE, GROUP BY and HAVING over the relation
    presentation.py   after the body: ORDER BY and LIMIT
    names.py          what an invented name may not spell
    derivation.py     the result a closed query produces, and the table it exports
    compound.py       members joined by set operators
    purpose.py        what a subquery is written for
    frame.py          where a query stands in its statement
    catalog.py        the stack of virtual tables a query is written over
    lifecycle.py      the rules for moving a query from one clause to the next
    writes.py         every write a query takes, guarded by the clause it belongs to
    virtual.py        the virtual table: the parts, bound to the clause machine
"""

from .catalog import Catalog
from .compound import SET_OPERATORS, Compound, SetOperator
from .contract import Contract
from .derivation import Output, Result, merge, result, table
from .expression import (
    STAR,
    Arithmetic,
    Call,
    Case,
    Column,
    Direction,
    Expr,
    Literal,
    Predicate,
    Star,
    Subquery,
    Window,
    narrowing,
)
from .frame import Frame
from .grouping import Grouping
from .names import Exclusion, NameUse
from .placement import placeable
from .presentation import Presentation
from .purpose import NESTING, Derivation, Existence, Membership, Purpose, Scalar
from .projection import Item, Projection
from .refinement import Refinement
from .operand import Operand
from .relation import Relation
from .selection import Selection
from .shape import Shape
from .sources import Sources
from .virtual import VirtualTable

__all__ = [
    "Arithmetic",
    "Call",
    "Case",
    "Catalog",
    "Column",
    "Compound",
    "Contract",
    "Direction",
    "Exclusion",
    "Expr",
    "Frame",
    "Grouping",
    "Item",
    "Literal",
    "NameUse",
    "Operand",
    "Output",
    "Predicate",
    "Presentation",
    "Purpose",
    "Derivation",
    "Existence",
    "Membership",
    "NESTING",
    "Scalar",
    "Projection",
    "Refinement",
    "Relation",
    "Result",
    "SET_OPERATORS",
    "STAR",
    "Selection",
    "SetOperator",
    "Shape",
    "Sources",
    "Star",
    "Subquery",
    "VirtualTable",
    "Window",
    "merge",
    "narrowing",
    "placeable",
    "result",
    "table",
]
