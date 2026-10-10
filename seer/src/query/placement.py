"""Placement: whether a FROM clause can still be written at all.

The algebra of `resolution.root` decides which tables the bare columns of the
projection need, and the alias scopes which table each alias may be. What
neither of them sees is the rule SQL applies across both: a bare column has to
be supplied by exactly one node of the FROM clause - and every alias is a node
that will be placed. So

    SELECT email, u.first_name FROM ...

needs `u` to be `users`, which supplies `email` as well, and the only FROM
clause left is `users AS u` alone: a bare `users` beside it would make
`email` ambiguous. And

    SELECT id, title, u.email FROM ...

has none at all - `title` needs `posts`, `u.email` needs `users`, and both
supply `id`.

`placeable` is that question: is there a table for every alias not placed
yet, and a set of bare tables for the algebra still to be satisfied with, such
that no bare column has two suppliers among them and the nodes already
placed. Placing an alias asserts its table to the algebra too
(`Conflicts.use_table`), so the search assumes each alias's table before it
completes the rest. The projection only offers a column that keeps the answer
yes, and the FROM clause only places a node that does, so a statement is never
written into a corner it cannot leave.

A table that may be placed once at most - the definition a recursive member
reads - counts against every node of it, whichever way it would be placed.

An alias may also be placed as a derived table, `(SELECT ...) AS u`, where the
query may still open one: a derived table exports what was read off the alias
and no name the projection uses bare, so it supplies no bare column and asks
nothing of the algebra. It is one more candidate, and always a clash-free one.

The search is exhaustive and small: an alias has a handful of candidate
tables, and the algebra still requires a handful more.
"""

from __future__ import annotations

from itertools import combinations, product
from typing import Sequence

from ..model import DERIVED, Schema, unqualify
from ..resolution import Conflicts, Root

def supplied(schema: Schema, table: str, bare: frozenset[str]) -> frozenset[str]:
    """The bare columns a node of `table` would supply."""

    definition = schema.tables.get(table)

    if definition is None:
        return frozenset()

    return frozenset(column for column in bare if column in definition.fields)

def _completions(
    root: Root,
    bare: frozenset[str],
    schema: Schema,
    claimed: frozenset[str],
    spent: frozenset[str],
) -> bool:
    """Whether some set of the tables `root` still requires satisfies it.

    Each table has to supply columns no node claims yet, and none may be one
    of the once-only tables a node is already `spent` on.
    """

    if root.is_satisfied():
        return True

    required: list[str] = sorted(root.get_required_tables() - spent)

    for size in range(1, len(required) + 1):
        for tables in combinations(required, size):
            supplies: list[frozenset[str]] = [supplied(schema, table, bare) for table in tables]

            if sum(len(part) for part in supplies) != len(frozenset().union(*supplies)):
                continue

            if frozenset().union(*supplies) & claimed:
                continue

            trial: Root = root.copy()

            if all(trial.use_table(table) for table in tables) and trial.is_satisfied():
                return True

    return False

def _spends(tables: Sequence[str], once: frozenset[str]) -> frozenset[str] | None:
    """The once-only tables among `tables`; `None` where one of them comes twice."""

    used: list[str] = [table for table in tables if table in once]

    return None if len(used) != len(set(used)) else frozenset(used)

def placeable(
    schema: Schema,
    conflicts: Conflicts,
    bare: frozenset[str],
    placed: Sequence[str] = (),
    once: frozenset[str] = frozenset(),
    derivable: bool = False,
) -> bool:
    """Whether the rest of the FROM clause can be placed beside `placed`, every bare column supplied once."""

    taken: frozenset[str] = frozenset()

    for node in placed:
        supplies: frozenset[str] = supplied(schema, unqualify(node)[0], bare)

        if supplies & taken:
            return False

        taken = taken | supplies

    placed_tables: list[str] = [unqualify(node)[0] for node in placed]

    scopes: list[tuple[str, frozenset[str]]] = conflicts.scopes.open()

    options: list[list[str]] = [
        sorted(candidates) + ([DERIVED] if derivable else []) for _, candidates in scopes
    ]

    for choice in product(*options):
        # A derived table supplies nothing and assumes nothing.
        assignment: tuple[str, ...] = tuple(table for table in choice if table != DERIVED)
        spent: frozenset[str] | None = _spends(placed_tables + list(assignment), once)

        if spent is None:
            continue

        claimed: frozenset[str] = taken
        clashes: bool = False

        for table in assignment:
            supplies = supplied(schema, table, bare)

            if supplies & claimed:
                clashes = True

                break

            claimed = claimed | supplies

        if clashes:
            continue

        trial: Root = conflicts.root.copy()

        if not all(trial.use_table(table) for table in sorted(set(assignment))):
            continue

        if _completions(trial, bare, schema, claimed, spent):
            return True

    return False
