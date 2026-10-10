"""Subqueries: `( SELECT ... )` wherever one may stand.

    <subquery> := "(" <query> ")"

A subquery is a query like any other - members, set operators, ORDER BY and
LIMIT, subqueries of its own - so its body is the statement's own `<query>`,
built once and shared by every place a subquery may stand: a value of the
projection, the right side of a comparison, the list of an `IN`, an `EXISTS`, a
table of the FROM clause.

What differs between those places is what comes after the closing bracket
and what the query around it does with the result, and both are handed to the
context when the subquery opens (`Context.begin_subquery`): the closing
bracket hands the result back and the grammar resumes where the caller said,
the way a call returns to its caller. The opening bracket is the caller's to
write, since `IN (` opens a list of literals just as well.

Every subquery is offered only while the nesting limit leaves room for it.
"""

from __future__ import annotations

from ..context import Commit
from ..query import Purpose
from ..runtime import Selector, Thunk
from . import statement as statements
from .combinators import dynamic, guard, lat, ws
from .selectors import select, step
from .tokens import RPAREN

_end: Selector = step(lambda ctx: ctx.end_subquery())
_resume: Thunk = dynamic(lambda ctx: [ctx.resumed])

_body: Thunk | None = None

def body() -> Thunk:
    """Everything after a subquery's `SELECT`, up to its closing bracket - built once."""

    global _body

    if _body is None:
        _body = ws(statements.query(statements.closing(RPAREN, _end, _resume)))

    return _body

def subquery(purpose: Purpose, resume: Thunk, commit: Commit | None = None) -> Thunk:
    """`SELECT ... )` for `purpose`, resuming at `resume`; `commit` hands the result over."""

    begin: Selector = select(lambda ctx, _matched: ctx.begin_subquery(purpose, resume, commit))

    return guard(lambda ctx: ctx.can_open_subquery(), lat("SELECT", begin, Thunk.deferred(body)))
