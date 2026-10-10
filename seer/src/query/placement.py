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
nothing of the algebra. That makes it the best any alias can be placed as -
whatever a table would let the algebra complete with, it can complete with
by itself - so where every alias may be one, only the algebra is left to ask.

Otherwise each alias is given one of its tables in turn. What the rest of the
search can still do depends only on the set of tables given so far - which
bare columns they claim, which once-only tables they spend, what the algebra
has left - so a set that failed once is not tried again, and the search stays
small however many aliases the projection opens.
"""

from __future__ import annotations

from typing import Sequence

from ..model import Schema, unqualify
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
    of the once-only tables a node is already `spent` on. The tables are tried
    in order, and a set the algebra refuses or that claims a column twice is
    not grown any further, since nothing added to it would mend that.
    """

    if root.is_satisfied():
        return True

    required: list[str] = sorted(root.get_required_tables() - spent)

    def search(start: int, trial: Root, claimed: frozenset[str]) -> bool:
        for position in range(start, len(required)):
            supplies: frozenset[str] = supplied(schema, required[position], bare)

            if supplies & claimed:
                continue

            grown: Root = trial.copy()

            if not grown.use_table(required[position]):
                continue

            if grown.is_satisfied() or search(position + 1, grown, claimed | supplies):
                return True

        return False

    return search(0, root, claimed)

def _assignments(
    root: Root,
    bare: frozenset[str],
    schema: Schema,
    scopes: Sequence[frozenset[str]],
    claimed: frozenset[str],
    spent: frozenset[str],
    once: frozenset[str],
) -> bool:
    """Whether every alias can be given one of the tables in `scopes`, and the algebra completed beside them.

    Two aliases may be given one table as long as it supplies no bare column
    and may be placed more than once.
    """

    failed: set[tuple[int, frozenset[str]]] = set()

    def search(
        position: int,
        tables: frozenset[str],
        trial: Root,
        claimed: frozenset[str],
        spent: frozenset[str],
    ) -> bool:
        if position == len(scopes):
            return _completions(trial, bare, schema, claimed, spent)

        # The tables given so far decide everything the rest depends on.
        if (position, tables) in failed:
            return False

        for table in sorted(scopes[position]):
            supplies: frozenset[str] = supplied(schema, table, bare)

            if supplies & claimed or table in spent:
                continue

            assumed: Root = trial

            if table not in tables:
                assumed = trial.copy()

                if not assumed.use_table(table):
                    continue

            if search(position + 1, tables | {table}, assumed, claimed | supplies, spent | (once & {table})):
                return True

        failed.add((position, tables))

        return False

    return search(0, frozenset(), root, claimed, spent)

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

    placed_tables: list[str] = [unqualify(node)[0] for node in placed if unqualify(node)[0] in once]

    if len(placed_tables) != len(set(placed_tables)):
        return False

    spent: frozenset[str] = frozenset(placed_tables)

    # Every alias left may be a derived table, which supplies nothing and
    # assumes nothing, so none of them can do better than to be one.
    if derivable:
        return _completions(conflicts.root, bare, schema, taken, spent)

    scopes: list[frozenset[str]] = [candidates for _, candidates in conflicts.scopes.open()]

    return _assignments(conflicts.root, bare, schema, scopes, taken, spent, once)
