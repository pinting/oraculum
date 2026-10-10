"""Purpose: what a subquery is written for, which decides what it has to produce.

A subquery is a query of its own, written inside another one, and where it
stands decides its contract (`contract.py`) the way a definition's frame does:

    Scalar       a value - `x = (SELECT MAX(id) FROM posts)` - so one column,
                 and one row: an aggregate over the whole query, never grouped
    Membership   the list of an `IN` - one column, as many rows as it likes
    Existence    the query of an `EXISTS` - anything at all
    Derivation   a table of the FROM clause - `(SELECT ...) AS d` - so every
                 column named, the ones the projection already read off `d`
                 among them, and none named like a column the projection
                 names bare, which `d` would make ambiguous

Subqueries nest, but not without end: `NESTING` is how many may be open at
once, counting from the statement's own queries.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..model import Kinds

# How many subqueries may be open inside one another.
NESTING: int = 2

class Purpose:
    __slots__ = ()

@dataclass(frozen=True)
class Scalar(Purpose):
    kinds: Kinds | None = None
    """The classes the value may have; `None` for any."""

@dataclass(frozen=True)
class Membership(Purpose):
    kinds: Kinds

@dataclass(frozen=True)
class Existence(Purpose):
    pass

@dataclass(frozen=True)
class Derivation(Purpose):
    alias: str | None = None
    """The alias the projection read the table through; `None` for a new one."""

    required: tuple[tuple[str, Kinds | None], ...] = ()
    """The columns the projection read off the alias, with the classes it read them as."""

    forbidden: frozenset[str] = frozenset()
    """The names the projection uses bare, which the table may not export."""
