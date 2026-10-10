"""Reserved names: what an invented name may not spell.

Every name the generator invents - an alias opened in the projection, the name
`AS` gives an aggregate, the name of a `WITH` definition - is an identifier
minus a reserved set, and the set is what keeps the statement readable one way
only. A name that spelled a keyword, a function, a table or a column would be
ambiguous with the token it shadows: `SELECT users.email` would open an alias
called `users`, `COUNT(*) AS COUNT` would name a column after the function
computing it, `WITH users AS (...)` would hide a table behind a query.

SQL compares unquoted identifiers **ignoring case**, so a reserved name is
reserved in every spelling: `USERS`, `Users` and `users` are one name, and two
definitions called `T` and `t` collide. An `Exclusion` stores its names lower
cased and the grammar excludes each of them case-insensitively.

The base set is the same for every use:

* the SQL keywords and every function name;
* every table and column name the query can see, through the whole stack.

Beyond it each use adds the names the query itself has introduced that the new
name could collide with:

* a **qualifier** may not be an item's output alias. It may repeat an alias
  already opened, since that is the same scope written again - but only as it
  was written, because any other spelling would be the same alias to SQL and a
  second scope to the resolver;
* an **output** alias may not be another output alias, nor an opened alias;
* a **definition** may not be named after anything the stack defines, which
  includes every definition before it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from ..model import KEYWORDS, Schema, function_names

class NameUse(Enum):
    QUALIFIER = "qualifier"
    """An alias opened by `<alias>.` in the projection."""

    OUTPUT = "output"
    """The name `AS` gives a projected item."""

def fold(names: Iterable[str]) -> frozenset[str]:
    """Names as SQL compares them."""

    return frozenset(name.lower() for name in names)

@dataclass(frozen=True)
class Exclusion:
    """What an invented name may not be."""

    forbidden: frozenset[str] = frozenset()
    """Folded names refused in every spelling."""

    respellings: frozenset[str] = frozenset()
    """Names that may be written again exactly as they are, and in no other spelling."""

    def allows(self, name: str) -> bool:
        folded: str = name.lower()

        if folded in self.forbidden:
            return False

        return name in self.respellings or folded not in fold(self.respellings)

    def including(self, *groups: Iterable[str]) -> "Exclusion":
        """This exclusion, refusing every spelling of `groups` too."""

        forbidden: set[str] = set(self.forbidden)

        for group in groups:
            forbidden.update(fold(group))

        return Exclusion(frozenset(forbidden), self.respellings)

    def respelling(self, names: Iterable[str]) -> "Exclusion":
        """This exclusion, allowing `names` only as written."""

        return Exclusion(self.forbidden, self.respellings | frozenset(names))

def base_reserved(schema: Schema, extra: Iterable[str] = ()) -> Exclusion:
    """Keywords, functions, every name `schema` defines, and `extra`."""

    return Exclusion().including(KEYWORDS, function_names(), schema.get_names(), extra)
