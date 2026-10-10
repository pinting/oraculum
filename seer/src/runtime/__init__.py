"""The kernel boundary: index drafts, the graph's values, and the engine.

Nothing in here knows what SQL is. The grammar is built from `Thunk`s and
`Node`s, the engine walks them through the kernel, and the `Context` they carry
is opaque to all three modules.
"""

from .backend import Algebra, JoinGraph, Label, Poly
from .engine import Engine, Head
from .factory import DraftKind, IndexDraft, IndexFactory, IndexSpec
from .thunk import Node, Selector, Thunk, ThunkFn

__all__ = [
    "Algebra",
    "DraftKind",
    "Engine",
    "Head",
    "IndexDraft",
    "IndexFactory",
    "IndexSpec",
    "JoinGraph",
    "Label",
    "Node",
    "Poly",
    "Selector",
    "Thunk",
    "ThunkFn",
]
