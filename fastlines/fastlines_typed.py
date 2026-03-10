from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

import fastlines as _fl

class Vocabulary:
    __slots__ = ("unit",)

    unit: _fl.Vocabulary

    def __init__(self, data: bytes, eos_id: int) -> None:
        self.unit = _fl.Vocabulary(data, eos_id)

    @classmethod
    def from_file_path(cls, file_path: str, eos_id: int) -> Vocabulary:
        instance = cls.__new__(cls)
        instance.unit = _fl.Vocabulary.from_file_path(file_path, eos_id)

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


class AhoCorasick:
    __slots__ = ("unit",)

    unit: _fl.AhoCorasick

    def __init__(self, vocabulary: Vocabulary) -> None:
        self.unit = _fl.AhoCorasick.new(vocabulary.unit)


class Lattice:
    __slots__ = ("unit",)

    unit: _fl.Lattice

    def __init__(self, input: str, vocabulary: Vocabulary, ac_base: AhoCorasick) -> None:
        self.unit = _fl.Lattice(input, vocabulary.unit, ac_base.unit)

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

    unit: _fl.TokTrie

    def __init__(self, vocabulary: Vocabulary) -> None:
        self.unit = _fl.TokTrie.new(vocabulary.unit)


class Expression:
    __slots__ = ("unit",)

    unit: _fl.Expression

    def __init__(self, input: str, vocabulary: Vocabulary, toktrie_base: TokTrie) -> None:
        self.unit = _fl.Expression(input, vocabulary.unit, toktrie_base.unit)

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
