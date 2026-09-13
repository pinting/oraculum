"""A typed facade over the `kernel` extension module.

The extension is built by PyO3 and carries no Python level types of its own, so
each class here wraps one of its classes, holds it as `unit`, and forwards to
it. Nothing is added on the way through: the point is the annotations, so that
a caller gets checking and completion over an API that is otherwise opaque.

`kernel.pyi` describes the same surface as stubs, for callers importing the
extension directly.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

import numpy as np
from numpy.typing import NDArray

import kernel as _kl

class Vocabulary:
    __slots__ = ("unit",)

    unit: _kl.Vocabulary

    def __init__(self, data: bytes, eos_id: int) -> None:
        self.unit = _kl.Vocabulary(data, eos_id)

    @classmethod
    def from_file_path(cls, file_path: str, eos_id: int) -> Vocabulary:
        instance = cls.__new__(cls)
        instance.unit = _kl.Vocabulary.from_file_path(file_path, eos_id)

        return instance

    def get_token_by_id(self, id: int) -> str | None:
        return self.unit.get_token_by_id(id)

    def get_id_by_token(self, token: str) -> int | None:
        return self.unit.get_id_by_token(token)

    def get_eos_id(self) -> int:
        return self.unit.get_eos_id()

    def get_tokens(self) -> list[str]:
        return self.unit.get_tokens()

    def get_ids(self) -> list[int]:
        return self.unit.get_ids()

    def get_token_by_idx(self, idx: int) -> str | None:
        return self.unit.get_token_by_idx(idx)

    def get_id_by_idx(self, idx: int) -> int | None:
        return self.unit.get_id_by_idx(idx)

class BooleanPolynomialRing:
    """Boolean polynomials over `GF(2)[t..]/(t^2 - t)`, as decision diagrams.

    A polynomial is the `int` id of a node in this ring's diagram. The diagram
    is hash consed, so equal ids mean equal polynomials; `0` is the zero
    polynomial and `1` the constant one. An id means nothing to another ring.
    """

    __slots__ = ("unit",)

    unit: _kl.BooleanPolynomialRing

    def __init__(self, names: Sequence[str]) -> None:
        self.unit = _kl.BooleanPolynomialRing(names)

    def one(self) -> int:
        return self.unit.one()

    def zero(self) -> int:
        return self.unit.zero()

    def mutual_exclusion(self, names: Sequence[str]) -> int:
        return self.unit.mutual_exclusion(names)

    def product(self, left: int, right: int) -> int:
        return self.unit.product(left, right)

    def sum(self, left: int, right: int) -> int:
        return self.unit.sum(left, right)

    def is_zero(self, poly: int) -> bool:
        return self.unit.is_zero(poly)

    def assume(self, poly: int, name: str) -> int:
        return self.unit.assume(poly, name)

    def constrained(self, poly: int) -> frozenset[str]:
        return self.unit.constrained(poly)

    def holds_empty(self, poly: int) -> bool:
        return self.unit.holds_empty(poly)

    def nonzero(self, poly: int, others: Sequence[int]) -> list[bool]:
        return self.unit.nonzero(poly, others)

    def viable(self, poly: int) -> frozenset[str]:
        return self.unit.viable(poly)

    def render(self, poly: int) -> str:
        return self.unit.render(poly)

    def term_count(self, poly: int) -> int:
        return self.unit.term_count(poly)

    def node_count(self) -> int:
        return self.unit.node_count()

    def memory_usage(self) -> int:
        return self.unit.memory_usage()

class Multigraph:
    """An undirected multigraph whose only mutation is vertex contraction.

    Vertices come from the edges alone; labels are stored and handed back,
    never examined. `copy` shares both the edges and the contraction state.
    """

    __slots__ = ("unit",)

    unit: _kl.Multigraph

    def __init__(self, edges: Iterable[tuple[str, str, Any]] | None = None) -> None:
        self.unit = _kl.Multigraph(edges)

    @classmethod
    def wrap(cls, unit: _kl.Multigraph) -> Multigraph:
        instance = cls.__new__(cls)
        instance.unit = unit

        return instance

    def copy(self) -> Multigraph:
        return Multigraph.wrap(self.unit.copy())

    def __contains__(self, node: str) -> bool:
        return node in self.unit

    def nodes(self) -> list[str]:
        return self.unit.nodes()

    def edges(self, node: str) -> list[tuple[str, Any]]:
        return self.unit.edges(node)

    def merge_vertices(self, head: str, other: str) -> bool:
        return self.unit.merge_vertices(head, other)

    def edge_count(self) -> int:
        return self.unit.edge_count()

    def memory_usage(self) -> int:
        return self.unit.memory_usage()

    def base_memory_usage(self) -> int:
        return self.unit.base_memory_usage()

    def __len__(self) -> int:
        return len(self.unit)

class AhoCorasick:
    __slots__ = ("unit",)

    unit: _kl.AhoCorasick

    def __init__(self, vocabulary: Vocabulary) -> None:
        self.unit = _kl.AhoCorasick.new(vocabulary.unit)

class Lattice:
    __slots__ = ("unit",)

    unit: _kl.Lattice

    def __init__(self, input: str, vocabulary: Vocabulary, ac_base: AhoCorasick) -> None:
        self.unit = _kl.Lattice(input, vocabulary.unit, ac_base.unit)

    def node_count(self) -> int:
        return self.unit.node_count()

    def transitions(self, node_id: int) -> NDArray[np.uint64]:
        return self.unit.transitions(node_id)

    def next(self, node_id: int, token_id: int) -> int | None:
        return self.unit.next(node_id, token_id)

    def accepting(self, node_id: int) -> bool | None:
        return self.unit.accepting(node_id)

    def memory_usage(self) -> int:
        return self.unit.memory_usage()

class TokTrie:
    __slots__ = ("unit",)

    unit: _kl.TokTrie

    def __init__(self, vocabulary: Vocabulary) -> None:
        self.unit = _kl.TokTrie.new(vocabulary.unit)

class Expression:
    __slots__ = ("unit",)

    unit: _kl.Expression

    def __init__(self, input: str, vocabulary: Vocabulary, toktrie_base: TokTrie) -> None:
        self.unit = _kl.Expression(input, vocabulary.unit, toktrie_base.unit)

    def node_count(self) -> int:
        return self.unit.node_count()

    def transitions(self, node_id: int) -> NDArray[np.uint64]:
        return self.unit.transitions(node_id)

    def next(self, node_id: int, token_id: int) -> int | None:
        return self.unit.next(node_id, token_id)

    def accepting(self, node_id: int) -> bool | None:
        return self.unit.accepting(node_id)

    def memory_usage(self) -> int:
        return self.unit.memory_usage()

class Factory:
    """The index registry: drafts in, ids out.

    Indexes are kept here rather than handed back, so one index backs every
    head that needs it and a spec is built at most once.
    """

    __slots__ = ("unit",)

    unit: _kl.Factory

    def __init__(self, vocabulary: Vocabulary, cache: bool = True) -> None:
        self.unit = _kl.Factory(vocabulary.unit, cache)

    @classmethod
    def wrap(cls, unit: _kl.Factory) -> Factory:
        instance = cls.__new__(cls)
        instance.unit = unit

        return instance

    def fork(self, cache: bool = True) -> Factory:
        return Factory.wrap(self.unit.fork(cache))

    def create(self, spec: _kl.IndexSpec) -> int | None:
        return self.unit.create(spec)

    def create_many(self, specs: Iterable[_kl.IndexSpec]) -> list[int | None]:
        return self.unit.create_many(specs)

    def lattice(self, word: str) -> int | None:
        return self.unit.lattice(word)

    def expression(self, pattern: str) -> int | None:
        return self.unit.expression(pattern)

    def group(self, include: int, excludes: Sequence[int]) -> int | None:
        """`include` minus every index in `excludes`."""

        return self.unit.group(include, excludes)

    def is_cached(self, spec: _kl.IndexSpec) -> bool:
        return self.unit.is_cached(spec)

    def label(self, index_id: int) -> str:
        return self.unit.label(index_id)

    def node_count(self, index_id: int) -> int:
        return self.unit.node_count(index_id)

    def memory_usage(self, index_id: int) -> int:
        return self.unit.memory_usage(index_id)

    def is_group(self, index_id: int) -> bool:
        return self.unit.is_group(index_id)

    @property
    def builds(self) -> int:
        return self.unit.builds

    def __len__(self) -> int:
        return len(self.unit)

class Runner:
    """The pool of active indexes, and the workers that drive them."""

    __slots__ = ("unit",)

    unit: _kl.Runner

    def __init__(self, factory: Factory, workers: int = 0) -> None:
        self.unit = _kl.Runner(factory.unit, workers)

    def set_resolver(self, callback: _kl.Resolver) -> None:
        self.unit.set_resolver(callback)

    def spawn(self, spec: _kl.IndexSpec | int, payload: Any) -> int | None:
        return self.unit.spawn(spec, payload)

    def spawn_many(self, items: Iterable[tuple[_kl.IndexSpec, Any]]) -> list[int]:
        return self.unit.spawn_many(items)

    def feed(self, token_id: int) -> bool:
        return self.unit.feed(token_id)

    def settle(self) -> None:
        self.unit.settle()

    def routes(self) -> NDArray[np.uint64]:
        return self.unit.routes()

    def heads(self) -> list[_kl.Head]:
        return self.unit.heads()

    def head(self, head_id: int) -> _kl.Head | None:
        return self.unit.head(head_id)

    def kill(self, head_id: int) -> bool:
        return self.unit.kill(head_id)

    def clear(self) -> None:
        self.unit.clear()

    def is_completed(self) -> bool:
        return self.unit.is_completed()

    def matched(self) -> str:
        return self.unit.matched()

    @property
    def factory(self) -> Factory:
        return Factory.wrap(self.unit.factory)

    @property
    def workers(self) -> int:
        return self.unit.workers

    @property
    def stats(self) -> tuple[int, int, int]:
        """Rounds of the resolve loop, heads notified, and heads created."""

        return self.unit.stats

    def __len__(self) -> int:
        return len(self.unit)
