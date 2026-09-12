"""The SQL SELECT syntax graph.

The language, which resolves its FROM clause by walking the foreign key graph
rather than by listing tables flat:

    SELECT <fields> FROM <entry> [, <entry>]* [WHERE <filters>] ;
    <entry>  := <table> [AS <alias>] [<join>]*
    <join>   := <join type> <table> [AS <alias>] ON <column> = <column>
    <fields> := <field ref> [, <field ref>]*
    <field ref> := <field> | <alias>.<field>
    <filters>   := <predicate> [(AND | OR) <predicate>]*
    <predicate> := [NOT] (<condition> | "(" <filters> ")")
    <condition> := <operand> <operator> <operand | literal>
                 | <operand> IS [NOT] NULL
    <operand>   := <column> | <qualifier>.<column>

Two loops shape the FROM clause: the outer one over entries is `from_entry`
plus `finish`, the inner one over joins is `joins`. The phase boundary ahead of
them is the `FROM` keyword, whose selector calls `Context.enter_from` to build
the join graph.

The WHERE clause sits behind a second boundary of the same shape. Its keyword
calls `Context.enter_where`, which fixes the virtual table the finished FROM
clause produced, and every condition is then gated on the types of that table's
columns. The type never enters the context: an operand knows its own `Field`,
so the restriction rides in the continuation the way `join_clause` already
carries its `Neighbor`.

Every combinator returns a `Thunk`, so nodes only exist once a context is
pushed through them, which is what lets the alternatives depend on what has
already been selected.
"""

from __future__ import annotations

from typing import Sequence

from .context import Context
from .engine import Node, Selector, Thunk
from .factory import IndexDraft
from .operators import Operator, TypeClass, classify, literal_for, operators_for
from .relation import Operand
from .relationships import JOIN_TYPES, JoinType, Neighbor
from .scopes import unqualify

IDENTIFIER: str = r"[a-zA-Z_][a-zA-Z0-9_]*"
WHITESPACE: str = r"[ \n\t]+"
COMMA: str = r"[ \n\t]*,[ \n\t]*"

# The brackets carry their own inner whitespace, so `(a = b)` and `( a = b )`
# are both reachable without an index that accepts the empty word.
LPAREN: str = r"\([ \n\t]*"
RPAREN: str = r"[ \n\t]*\)"

# How deep the parentheses of a WHERE clause may nest. The graph is generative,
# so without a cap nothing would ever stop offering another `(`.
NESTING_LIMIT: int = 3

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

    An alias is invented by whoever is generating - nothing in the schema says
    what it should be called - so the only shape available is the identifier
    pattern. That pattern is too wide on its own: `users` matches it, and so
    does `SELECT`, which would make `SELECT users.email` open an alias named
    after a table and `SELECT SELECT.x` legal.

    So the index is a group: the identifier pattern minus one lattice per
    reserved word, table and field. While an exclusion still spells what has
    been matched the group refuses to end, and generation has to go on until
    the identifier grows past it - `user` is blocked, `users` is blocked,
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

def _enter_where(ctx: Context, _matched: str) -> Context:
    """The second boundary: the FROM clause is closed, fix the virtual table."""

    clone: Context = ctx.copy()

    clone.enter_where()

    return clone

def _select_condition(left: Operand, operator: Operator) -> Selector:
    """Commit a binary condition once its right hand side has been written.

    The matched text *is* the right hand side, whether that was a column
    spelling or a literal, so one factory covers both.
    """

    def selector(ctx: Context, matched: str) -> Context:
        clone: Context = ctx.copy()

        clone.use_filter(f"{left.text} {operator} {matched}")

        return clone

    return selector

def _select_predicate(left: Operand, operator: Operator) -> Selector:
    """Commit a unary condition, whose operator is its last token."""

    def selector(ctx: Context, _matched: str) -> Context:
        clone: Context = ctx.copy()

        clone.use_filter(f"{left.text} {operator}")

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

# -- WHERE ----------------------------------------------------------------

def right_side(left: Operand, operator: Operator, next: Thunk) -> Thunk:
    """What may stand opposite `left`: a column of its class, or a literal.

    This is the whole of the restriction. `left` was fixed by the caller, so
    its class is a constant here and the alternatives are simply the operands
    that share it - plus the pattern that spells a literal of that class, where
    the class has one. A class with no pattern, and `UNKNOWN` above all, is
    comparable to columns only.
    """

    kind: TypeClass = classify(left.field.type)

    def call(ctx: Context) -> list[Node]:
        options: list[Thunk] = []

        for right in ctx.get_operands(kind):
            # Comparing a column with itself says nothing, however it is spelled.
            if left.same_column(right):
                continue

            options.append(lat(right.text, _select_condition(left, operator), next))

        pattern: str | None = literal_for(kind)

        if pattern is not None:
            options.append(exp(pattern, _select_condition(left, operator), next))

        return branch(options).call(ctx) or []

    return Thunk.new(call)

def operator_choices(left: Operand, next: Thunk) -> Thunk:
    """The operators `left`'s type admits, each carrying its right hand side.

    A unary operator ends the condition, so it takes the selector itself; a
    binary one defers that to whatever `right_side` offers.
    """

    def call(ctx: Context) -> list[Node]:
        options: list[Thunk] = []

        for operator in operators_for(left.field):
            if operator.is_unary:
                options.append(
                    lat(str(operator), _select_predicate(left, operator), next)
                )
            else:
                options.append(
                    lat(str(operator), None, ws(right_side(left, operator, next)))
                )

        return branch(options).call(ctx) or []

    return Thunk.new(call)

def condition(next: Thunk) -> Thunk:
    """One comparison over the virtual table.

    The operand lattice is emitted once and its operators open only behind it,
    so a step here costs a head per column rather than a head per column and
    operator pair.
    """

    def call(ctx: Context) -> list[Node]:
        options: list[Thunk] = [
            lat(operand.text, None, ws(operator_choices(operand, next)))
            for operand in ctx.get_operands()
        ]

        return branch(options).call(ctx) or []

    return Thunk.new(call)

def predicate(next: Thunk, depth: int) -> Thunk:
    """One condition, optionally parenthesised, optionally negated."""

    options: list[Thunk] = [condition(next)]

    if depth > 0:
        closing: Thunk = exp(RPAREN, None, next)

        options.append(
            exp(LPAREN, None, Thunk.deferred(lambda: filters(closing, depth - 1)))
        )

    inner: Thunk = branch(options)

    return branch([inner, lat("NOT", None, ws(inner))])

def connective(next: Thunk) -> Thunk:
    return branch([
        lat("AND", None, ws(next)),
        lat("OR", None, ws(next)),
    ])

def filters(next: Thunk, depth: int) -> Thunk:
    """`<predicate> [(AND | OR) <predicate>]*`, flat on purpose.

    Precedence is a parser's problem. Layering disjunction over conjunction
    would produce exactly the strings this one loop produces, since nothing
    here has to recover the tree afterwards; the parentheses of `predicate` are
    what add structure a reader can see, and they are where the cost is.
    """

    fork: Thunk = branch([
        next,
        Thunk.deferred(lambda: ws(connective(filters(next, depth)))),
    ])

    return predicate(fork, depth)

def where_clause(next: Thunk) -> Thunk:
    """An optional `WHERE <filters>` between the FROM clause and the terminator."""

    return branch([
        next,
        ws(lat("WHERE", _enter_where, ws(filters(next, NESTING_LIMIT)))),
    ])

# -- root -----------------------------------------------------------------

def root() -> Thunk:
    """`SELECT <fields> FROM <entry> [, <entry>]* [WHERE <filters>] ;`"""

    next: Thunk = Thunk.terminal()
    next = lat(";", None, next)
    next = where_clause(next)
    next = from_clause(next)
    next = ws(next)
    next = lat("FROM", _enter_from, next)
    next = fields(ws(next))
    next = ws(next)

    return lat("SELECT", None, next)
