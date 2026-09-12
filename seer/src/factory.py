"""Index construction on top of the `kernel` Rust library.

The kernel never hands an index back. A `IndexDraft` describes the one a graph
node wants, the factory turns it into a real index and keeps it, and what comes
back is an id. Heads are then spawned onto that id, and the kernel walks them
internally.

Three kinds of draft exist, mirroring the kernel:

* a **lattice** matches a constant string through Aho-Corasick;
* an **expression** matches a regular expression through a TokTrie backed DFA;
* a **group** is one inclusion minus any number of exclusions, and is what
  alias resolution is built from - see `graph.alias`.

A group is drafted from other drafts, but the kernel wants the *ids* of its
members, so `spec` builds them first. That is cheap after the first time: the
members of an alias group are one shared identifier expression plus one tiny
lattice per excluded name, and all of them are memoised.

Indexes are immutable and carry no position - the position lives in the
kernel's `Memory`, one per head - which is what lets a single index back every
node that asks for it and be shared across the worker pool.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Sequence

import kernel as kl

class DraftKind(Enum):
    LATTICE = "lattice"
    EXPRESSION = "expression"
    GROUP = "group"

# What the kernel accepts in place of a built index: `("lattice", "SELECT")`,
# `("expression", "[a-z]+")` or `("group", include_id, [exclude_id, ...])`.
IndexSpec = tuple

class IndexDraft:
    """A hashable description of an index that has not been built yet."""

    __slots__ = ("kind", "value", "excludes")

    def __init__(
        self,
        kind: DraftKind,
        value: "str | IndexDraft",
        excludes: Iterable["IndexDraft"] = (),
    ) -> None:
        self.kind = kind
        self.value = value
        self.excludes: tuple[IndexDraft, ...] = tuple(excludes)

    @classmethod
    def lattice(cls, word: str) -> "IndexDraft":
        return cls(DraftKind.LATTICE, word)

    @classmethod
    def expression(cls, pattern: str) -> "IndexDraft":
        return cls(DraftKind.EXPRESSION, pattern)

    @classmethod
    def group(
        cls, include: "IndexDraft", excludes: Iterable["IndexDraft"]
    ) -> "IndexDraft":
        """`include` minus everything in `excludes`.

        Either side may itself be a group, so subtractions nest.
        """

        return cls(DraftKind.GROUP, include, excludes)

    @property
    def include(self) -> "IndexDraft":
        """The inclusion of a group draft."""

        assert self.kind is DraftKind.GROUP and isinstance(self.value, IndexDraft)

        return self.value

    def label(self) -> str:
        """The shape this draft matches, as the kernel reports it for a head."""

        if self.kind is DraftKind.GROUP:
            return self.include.label()

        assert isinstance(self.value, str)

        return self.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IndexDraft):
            return NotImplemented

        return (
            self.kind is other.kind
            and self.value == other.value
            and self.excludes == other.excludes
        )

    def __hash__(self) -> int:
        return hash((self.kind, self.value, self.excludes))

    def __repr__(self) -> str:
        if self.kind is DraftKind.GROUP:
            return f"IndexDraft.group({self.value!r}, -{len(self.excludes)})"

        return f"IndexDraft.{self.kind.value}({self.value!r})"

class IndexFactory:
    """Drafts in, index ids out.

    A thin layer over `kernel.Factory`: it resolves the members of a group
    draft into ids and leaves everything else - building, memoising,
    single-flight across threads - to the kernel.
    """

    __slots__ = ("_vocabulary", "_unit", "_specs", "_cache")

    def __init__(
        self,
        vocabulary: kl.Vocabulary,
        cache: bool = True,
        unit: kl.Factory | None = None,
    ) -> None:
        self._vocabulary = vocabulary
        self._unit = unit if unit is not None else kl.Factory(vocabulary, cache)
        self._cache = cache
        self._specs: dict[IndexDraft, IndexSpec] = {}

    @property
    def unit(self) -> kl.Factory:
        """The kernel factory, for handing to a `kernel.Runner`."""

        return self._unit

    @property
    def vocabulary(self) -> kl.Vocabulary:
        return self._vocabulary

    @property
    def builds(self) -> int:
        """Number of indexes actually constructed, ignoring cache hits."""

        return self._unit.builds

    def fork(self, cache: bool = True) -> "IndexFactory":
        """A factory with an empty registry but the same bases.

        Building the Aho-Corasick and TokTrie bases costs about half a second
        and depends only on the vocabulary, so a cold registry should never pay
        for them twice.
        """

        return IndexFactory(self._vocabulary, cache, unit=self._unit.fork(cache))

    def spec(self, draft: IndexDraft) -> IndexSpec | None:
        """The kernel spec for `draft`, building any group members it needs.

        `None` when a member cannot be built, which drops the node rather than
        failing the expansion.
        """

        if draft.kind is not DraftKind.GROUP:
            return (draft.kind.value, draft.value)

        known: IndexSpec | None = self._specs.get(draft)

        if known is not None:
            return known

        # The members are built as one batch rather than one at a time: an
        # alias group holds a lattice per reserved word, table and field, and
        # the kernel spreads a batch over its worker pool with the GIL dropped.
        members: tuple[IndexDraft, ...] = (draft.include,) + draft.excludes
        specs: list[IndexSpec | None] = [self.spec(member) for member in members]

        if any(spec is None for spec in specs):
            return None

        built: list[int | None] = self._unit.create_many(specs)

        if any(index is None for index in built):
            return None

        spec: IndexSpec = ("group", built[0], built[1:])

        if self._cache:
            self._specs[draft] = spec

        return spec

    def create_index(self, draft: IndexDraft) -> int | None:
        """Build the index for `draft` and return its id, or `None`."""

        spec: IndexSpec | None = self.spec(draft)

        if spec is None:
            return None

        return self._unit.create(spec)

    def create_many(self, drafts: Sequence[IndexDraft]) -> list[int | None]:
        """Build a batch, spread over the kernel's worker pool."""

        specs: list[IndexSpec | None] = [self.spec(draft) for draft in drafts]
        buildable: list[IndexSpec] = [spec for spec in specs if spec is not None]
        built: list[int | None] = self._unit.create_many(buildable)

        result: list[int | None] = []
        position: int = 0

        for spec in specs:
            if spec is None:
                result.append(None)

                continue

            result.append(built[position])

            position += 1

        return result

    def is_cached(self, draft: IndexDraft) -> bool:
        """Whether `create_index` would return without building anything."""

        if draft.kind is DraftKind.GROUP:
            spec: IndexSpec | None = self._specs.get(draft)

            if spec is None:
                return False
        else:
            spec = (draft.kind.value, draft.value)

        return self._unit.is_cached(spec)

    def label(self, index_id: int) -> str:
        return self._unit.label(index_id)

    def memory_usage(self, index_id: int) -> int:
        return self._unit.memory_usage(index_id)

    def __len__(self) -> int:
        return len(self._unit)
