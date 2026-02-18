from __future__ import annotations

from typing import Final
import numpy as np
from numpy.typing import NDArray

import fastlines as _fl

FAST_HASH_DFA: Final[int] = _fl.FAST_HASH_DFA
DOUBLE_HASH_DFA: Final[int] = _fl.DOUBLE_HASH_DFA
FLAT_DFA: Final[int] = _fl.FLAT_DFA
PGM_DFA: Final[int] = _fl.PGM_DFA

AC_CONTIGUOUS_NFA: Final[int] = _fl.AC_CONTIGUOUS_NFA
AC_NONCONTIGUOUS_NFA: Final[int] = _fl.AC_NONCONTIGUOUS_NFA
AC_DFA: Final[int] = _fl.AC_DFA

VALID_BITS: Final[set[int]] = {16, 32, 64}


def _validate_bits(bits: int, name: str) -> int:
    if bits not in VALID_BITS:
        raise ValueError(f"{name} must be one of {VALID_BITS}, got {bits}")

    return bits // 8


class Vocabulary:
    __slots__ = ("unit",)

    unit: _fl.Vocabulary

    def __init__(self, data: bytes, eos_id: int, t_size: int) -> None:
        t_bytes = _validate_bits(t_size, "t_size")

        self.unit = _fl.Vocabulary(data, eos_id, t_bytes)

    @classmethod
    def from_file_path(cls, file_path: str, eos_id: int, t_size: int) -> Vocabulary:
        t_bytes = _validate_bits(t_size, "t_size")

        instance = cls.__new__(cls)
        instance.unit = _fl.Vocabulary.from_file_path(file_path, eos_id, t_bytes)

        return instance

    def get_token_by_id(self, id: int) -> str | None:
        return self.unit.get_token_by_id(id)

    def get_id_by_token(self, token: str) -> int | None:
        return self.unit.get_id_by_token(token)

    def get_eos_id(self) -> int:
        return self.unit.get_eos_id()


class AhoCorasick:
    __slots__ = ("unit",)

    unit: _fl.AhoCorasick

    def __init__(self, vocabulary: Vocabulary, kind: int) -> None:
        self.unit = _fl.AhoCorasick.new(vocabulary.unit, kind)


class Lattice:
    __slots__ = ("unit",)

    unit: _fl.Lattice

    def __init__(self, input: str, vocabulary: Vocabulary, ac_base: AhoCorasick) -> None:
        self.unit = _fl.Lattice(input, vocabulary.unit, ac_base.unit)

    def start(self) -> int:
        return self.unit.start()

    def transitions(self, node_id: int) -> NDArray[np.uint64]:
        return self.unit.transitions(node_id)

    def next(self, node_id: int, token_id: int) -> int | None:
        return self.unit.next(node_id, token_id)

    def memory_usage(self) -> int:
        return self.unit.memory_usage()


class TokTrie:
    __slots__ = ("unit",)

    unit: _fl.TokTrie

    def __init__(
        self,
        vocabulary: Vocabulary,
        dfa_type: int,
        n_size: int,
        t_size: int,
    ) -> None:
        n_bytes = _validate_bits(n_size, "n_size")
        t_bytes = _validate_bits(t_size, "t_size")

        self.unit = _fl.TokTrie.new(vocabulary.unit, dfa_type, n_bytes, t_bytes)


class Expression:
    __slots__ = ("unit",)

    unit: _fl.Expression

    def __init__(self, input: str, vocabulary: Vocabulary, toktrie_base: TokTrie) -> None:
        self.unit = _fl.Expression(input, vocabulary.unit, toktrie_base.unit)

    def start(self) -> int:
        return self.unit.start()

    def transitions(self, node_id: int) -> NDArray[np.uint64]:
        return self.unit.transitions(node_id)

    def next(self, node_id: int, token_id: int) -> int | None:
        return self.unit.next(node_id, token_id)

    def memory_usage(self) -> int:
        return self.unit.memory_usage()
