"""The SQL SELECT syntax graph.

    tokens.py         the patterns separators and identifiers are spelled with
    combinators.py    lattices, expressions, branches, guards and names
    selectors.py      matched text into context operations, on a copy
    values/          the values an item is written as, before FROM exists
    operands.py       the values of the closed relation, typed as they are written
    projection.py     the item list, each item committed on the separator after it
    source.py         FROM entries and the joins off them
    conditions.py     the condition grammar, over whichever operands a clause names
    filter.py         WHERE
    grouping.py       GROUP BY and HAVING
    presentation.py   ORDER BY and LIMIT
    statement.py      the statement, end to end: definitions, compounds, the main query
"""

from .combinators import branch, dynamic, exp, guard, keyword, lat, name, ws
from .statement import root

__all__ = [
    "branch",
    "dynamic",
    "exp",
    "guard",
    "keyword",
    "lat",
    "name",
    "root",
    "ws",
]
