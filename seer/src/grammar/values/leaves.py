"""The leaves of a value: a column, bare or qualified, and a literal."""

from __future__ import annotations

from ...context import Context
from ...model import LITERALS, Kinds, TypeClass
from ...query import Column, Literal, NameUse
from ...runtime import Selector, Thunk
from ..combinators import branch, dot, dynamic, exp, lat, name
from ..selectors import select
from .position import Position, Then

# -- selectors -------------------------------------------------------------

_open_qualifier: Selector = select(lambda ctx, matched: ctx.query.open_qualifier(matched))
_capture: Selector = select(lambda ctx, matched: ctx.capture(matched))

def _use_column(column: str, kinds: Kinds | None) -> Selector:
    return select(lambda ctx, _matched: ctx.query.use_column(column, kinds))

def column_ref(position: Position, then: Then) -> Thunk:
    """A column bare, or `<alias>.<column>`, which opens the alias first."""

    def columns(ctx: Context) -> list[Thunk]:
        selection = ctx.query.selection
        qualifier: str = selection.qualifier

        return [
            lat(column, _use_column(column, position.kinds), then(Column(qualifier, column)))
            for column in selection.columns(position.kinds)
        ]

    bare: Thunk = dynamic(columns)
    after: Thunk = dot(bare)

    fresh: Thunk = name(
        lambda ctx: ctx.query.selection.reserved(NameUse.QUALIFIER, position.kinds),
        _open_qualifier,
        after,
    )

    def qualifiers(ctx: Context) -> list[Thunk]:
        selection = ctx.query.selection

        # An invented name is offered where a new alias could still supply a
        # column. Where none could, only the aliases that still can are
        # written, by name - an identifier pattern would take a new one too.
        if selection.can_open(position.kinds):
            return [fresh]

        return [lat(alias, _open_qualifier, after) for alias in selection.useful(position.kinds)]

    return branch([dynamic(qualifiers), bare])

def literal(position: Position, then: Then) -> Thunk:
    """A literal of every class the position allows."""

    def of(kind: TypeClass) -> Thunk:
        return exp(LITERALS[kind], _capture, dynamic(lambda ctx: [then(Literal(ctx.captured, kind))]))

    return branch([of(kind) for kind in position.classes()])
