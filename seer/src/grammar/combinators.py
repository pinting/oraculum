"""The combinators every clause of the grammar is built from.

Every combinator returns a `Thunk`, so nodes only exist once a context is
pushed through them, which is what lets the alternatives depend on what has
already been selected.
"""

from __future__ import annotations

import functools
from typing import Callable, Sequence

from ..context import Context
from ..query import Exclusion
from ..runtime import IndexDraft, Node, Selector, Thunk
from .tokens import COMMA, IDENTIFIER, WHITESPACE, insensitive

def expand(ctx: Context, thunks: Sequence[Thunk]) -> list[Node]:
    """Every node the alternatives offer under `ctx`, in order."""

    nodes: list[Node] = []

    for thunk in thunks:
        children: list[Node] | None = thunk.call(ctx)

        if children:
            nodes.extend(children)

    return nodes

def branch(thunks: Sequence[Thunk]) -> Thunk:
    """A thunk offering every alternative at once."""

    return Thunk.new(lambda ctx: expand(ctx, thunks))

def dynamic(build: Callable[[Context], Sequence[Thunk]]) -> Thunk:
    """A thunk whose alternatives are read off the context it is called with."""

    return Thunk.new(lambda ctx: expand(ctx, build(ctx)))

def guard(predicate: Callable[[Context], bool], next: Thunk) -> Thunk:
    """`next`, but only where the context allows it."""

    return Thunk.new(lambda ctx: (next.call(ctx) or []) if predicate(ctx) else [])

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

def keyword(word: str, selector: Selector, next: Thunk) -> Thunk:
    """`<ws> WORD`: a keyword stepped up to from whatever precedes it."""

    return ws(lat(word, selector, next))

@functools.cache
def exclusions(exclusion: Exclusion) -> tuple[IndexDraft, ...]:
    """One draft per reserved name, each matching every spelling it is refused in.

    Memoised: an exclusion is a value, and the few the grammar asks for are
    asked for at every name it offers.
    """

    drafts: list[IndexDraft] = [
        IndexDraft.expression(insensitive(word)) for word in sorted(exclusion.forbidden)
    ]

    # A name that may be repeated as written refuses its other spellings only:
    # every case of it, minus the one that is allowed.
    drafts.extend(
        IndexDraft.group(IndexDraft.expression(insensitive(word)), [IndexDraft.lattice(word)])
        for word in sorted(exclusion.respellings)
    )

    return tuple(drafts)

def name(reserved: Callable[[Context], Exclusion], selector: Selector, next: Thunk) -> Thunk:
    """Match a name someone invents: an identifier that spells nothing else.

    A name is invented by whoever is generating - nothing in the schema says
    what an alias should be called - so the only shape available is the
    identifier pattern. That pattern is too wide on its own: `users` matches
    it, and so does `SELECT`, which would make `SELECT users.email` open an
    alias named after a table and `SELECT SELECT.x` legal.

    So the index is a group: the identifier pattern minus one exclusion per
    reserved name, each spelling that name in any case. While an exclusion
    still spells what has been matched the group refuses to end, and
    generation has to go on until the identifier grows past it - `user` is
    allowed, `users` and `USERS` are blocked, `users2` is allowed again.

    Which names are reserved depends on what the name is for, so the caller
    says, as a question to the context.
    """

    def call(ctx: Context) -> list[Node]:
        draft: IndexDraft = IndexDraft.group(
            IndexDraft.expression(IDENTIFIER),
            exclusions(reserved(ctx)),
        )

        return [Node(draft, ctx, selector, next)]

    return Thunk.new(call)
