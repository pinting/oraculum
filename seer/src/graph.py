"""The SQL SELECT syntax graph.

`seer/src/graph.rs` rebuilt on the modelling of
`experiments/9-advanced-modelling`. The Rust graph could only emit a flat table
list:

    SELECT <fields> FROM <tables>;

The experiment resolves the FROM clause by walking the foreign key graph
instead, so the language grows a JOIN:

    SELECT <fields> FROM <entry> [, <entry>]* ;
    <entry>  := <table> [AS <alias>] [<join>]*
    <join>   := <join type> <table> [AS <alias>] ON <column> = <column>
    <fields> := <field ref> [, <field ref>]*
    <field ref> := <field> | <alias>.<field>

The two menu loops of the experiment's TUI map onto the graph directly. Its
outer FROM loop is `from_entry` plus `finish`, its inner JOIN loop is `joins`,
and the phase boundary between them is the `FROM` keyword, whose selector calls
`Context.enter_from` to build the join graph.

Every combinator still returns a `Thunk`, so nodes only exist once a context is
pushed through them, which is what lets the alternatives depend on what has
already been selected.
"""

from __future__ import annotations

from typing import Sequence

from .context import Context
from .engine import Node, Selector, Thunk
from .factory import IndexDraft
from .relationships import JOIN_TYPES, JoinType, Neighbor
from .scopes import unqualify

IDENTIFIER: str = r"[a-zA-Z_][a-zA-Z0-9_]*"
WHITESPACE: str = r"[ \n\t]+"
COMMA: str = r"[ \n\t]*,[ \n\t]*"

def branch(thunks: Sequence[Thunk]) -> Thunk:
    """A thunk offering every alternative at once."""

    def call(ctx: Context) -> list[Node]:
        nodes: list[Node] = []

        for thunk in thunks:
            children: list[Node] | None = thunk.call(ctx)

            if children:
                nodes.extend(children)

        return nodes

    return Thunk.new(call)

def lat(word: str, selector: Selector, next: Thunk) -> Thunk:
    """Match a constant string via an Aho-Corasick lattice."""

    draft: IndexDraft = IndexDraft.lattice(word)

    return Thunk.new(lambda ctx: [Node(draft, ctx, selector, next)])

def exp(pattern: str, selector: Selector, next: Thunk) -> Thunk:
    """Match a regular expression via a TokTrie-backed DFA."""

    draft: IndexDraft = IndexDraft.expression(pattern)

    return Thunk.new(lambda ctx: [Node(draft, ctx, selector, next)])

def ws(next: Thunk) -> Thunk:
    return exp(WHITESPACE, None, next)

def comma(next: Thunk) -> Thunk:
    return exp(COMMA, None, next)

def dot(next: Thunk) -> Thunk:
    return lat(".", None, next)

def alias(selector: Selector, next: Thunk) -> Thunk:
    """Match an alias: an identifier that spells nothing else.

    An alias is invented by whoever is generating -- nothing in the schema says
    what it should be called -- so the only shape available is the identifier
    pattern. That pattern is too wide on its own: `users` matches it, and so
    does `SELECT`, which would make `SELECT users.email` open an alias named
    after a table and `SELECT SELECT.x` legal.

    So the index is a group: the identifier pattern minus one lattice per
    reserved word, table and field. While an exclusion still spells what has
    been matched the group refuses to end, and generation has to go on until
    the identifier grows past it -- `user` is blocked, `users` is blocked,
    `users2` is not.
    """

    def call(ctx: Context) -> list[Node]:
        draft: IndexDraft = IndexDraft.group(
            IndexDraft.expression(IDENTIFIER),
            [IndexDraft.lattice(name) for name in ctx.get_reserved_names()],
        )

        return [Node(draft, ctx, selector, next)]

    return Thunk.new(call)

# -- selectors ------------------------------------------------------------

def _select_field(ctx: Context, matched: str) -> Context:
    clone: Context = ctx.copy()

    clone.use_field(matched)

    return clone

def _select_namespace(ctx: Context, matched: str) -> Context:
    clone: Context = ctx.copy()

    clone.set_current_namespace(matched)

    return clone

def _enter_from(ctx: Context, _matched: str) -> Context:
    """The phase boundary: field selection is over, build the join graph."""

    clone: Context = ctx.copy()

    clone.enter_from()

    return clone

def _select_table(node: str) -> Selector:
    def selector(ctx: Context, _matched: str) -> Context:
        clone: Context = ctx.copy()

        clone.use_table(node)

        return clone

    return selector

def _select_join(neighbor: Neighbor, join_type: JoinType) -> Selector:
    def selector(ctx: Context, _matched: str) -> Context:
        clone: Context = ctx.copy()

        clone.join_table(neighbor, join_type)

        return clone

    return selector

# -- fields ---------------------------------------------------------------

def field(next: Thunk) -> Thunk:
    """One field name, restricted to those the current namespace still allows."""

    def call(ctx: Context) -> list[Node]:
        return [
            Node(IndexDraft.lattice(name), ctx, _select_field, next)
            for name in ctx.get_fields()
        ]

    return Thunk.new(call)

def namespace_field(next: Thunk) -> Thunk:
    """An `<alias>.<field>` reference, which opens the alias scope."""

    return alias(_select_namespace, dot(field(next)))

def fields(next: Thunk) -> Thunk:
    """A comma separated field list, qualified or not."""

    fork: Thunk = branch([
        next,
        Thunk.deferred(lambda: comma(fields(next))),
    ])

    return branch([
        namespace_field(fork),
        field(fork),
    ])

# -- FROM / JOIN ----------------------------------------------------------

def node_name(node: str, selector: Selector, next: Thunk) -> Thunk:
    """Emit a node as `table` or `table AS alias`, selecting on the alias."""

    table, alias = unqualify(node)

    if not alias:
        return lat(table, selector, next)

    tail: Thunk = lat(alias, selector, next)
    tail = ws(tail)
    tail = lat("AS", None, tail)
    tail = ws(tail)

    return lat(table, None, tail)

def from_entry(next: Thunk) -> Thunk:
    """One FROM entry: a required table, then any number of joins off it."""

    def call(ctx: Context) -> list[Node]:
        nodes: list[Node] = []

        for node in ctx.get_required_tables():
            entry: Thunk = node_name(
                node,
                _select_table(node),
                Thunk.deferred(lambda: joins(next)),
            )

            children: list[Node] | None = entry.call(ctx)

            if children:
                nodes.extend(children)

        return nodes

    return Thunk.new(call)

def join_clause(neighbor: Neighbor, join_type: JoinType, next: Thunk) -> Thunk:
    """`<join type> <table> [AS <alias>] ON <column> = <column>`.

    The selector sits on the last token, so the join is only committed once the
    whole clause has been written.
    """

    tail: Thunk = lat(neighbor.dst_field, _select_join(neighbor, join_type), next)
    tail = ws(tail)
    tail = lat("=", None, tail)
    tail = ws(tail)
    tail = lat(neighbor.src_field, None, tail)
    tail = ws(tail)
    tail = lat("ON", None, tail)
    tail = ws(tail)
    tail = node_name(neighbor.table, None, tail)
    tail = ws(tail)

    return lat(str(join_type), None, tail)

def joins(next: Thunk) -> Thunk:
    """Zero or more JOINs off the current entry, then finish it."""

    def call(ctx: Context) -> list[Node]:
        options: list[Thunk] = [finish(next)]

        for neighbor in ctx.get_joinable_neighbors():
            for join_type in JOIN_TYPES:
                options.append(ws(join_clause(
                    neighbor,
                    join_type,
                    Thunk.deferred(lambda: joins(next)),
                )))

        return branch(options).call(ctx) or []

    return Thunk.new(call)

def finish(next: Thunk) -> Thunk:
    """End the entry: continue the statement, or start another FROM entry."""

    def call(ctx: Context) -> list[Node]:
        if ctx.is_satisfied():
            return next.call(ctx) or []

        return comma(from_entry(next)).call(ctx) or []

    return Thunk.new(call)

def from_clause(next: Thunk) -> Thunk:
    return from_entry(next)

# -- root -----------------------------------------------------------------

def root() -> Thunk:
    """`SELECT <fields> FROM <entry> [, <entry>]* ;`"""

    next: Thunk = Thunk.terminal()
    next = lat(";", None, next)
    next = from_clause(next)
    next = ws(next)
    next = lat("FROM", _enter_from, next)
    next = fields(ws(next))
    next = ws(next)

    return lat("SELECT", None, next)
