from __future__ import annotations

import time
import numpy as np
from numpy.typing import NDArray
import sys

import fastlines_typed as fl

def main() -> None:
    try:
        try:
            t0: float = time.perf_counter()
            vocabulary: fl.Vocabulary = fl.Vocabulary.from_file_path("../vocabulary.tiktoken", 1, 32)
            t1: float = time.perf_counter()

        except Exception:
            print("Error: vocabulary.tiktoken file not found or failed to load.")

            return

        print(f"Vocabulary loaded ({(t1 - t0) * 1000:.2f} ms)")

        t0 = time.perf_counter()
        ac_base: fl.AhoCorasick = fl.AhoCorasick(vocabulary, fl.AC_CONTIGUOUS_NFA)
        t1 = time.perf_counter()

        print(f"Lattice base (AhoCorasick) built ({(t1 - t0) * 1000:.2f} ms)")

        t0 = time.perf_counter()
        toktrie_base: fl.TokTrie = fl.TokTrie(vocabulary, fl.FLAT_DFA, 32, 32)
        t1 = time.perf_counter()

        print(f"Expression base (TokTrie) built with FlatDFA<32, 32> config ({(t1 - t0) * 1000:.2f} ms)")

        indexes: list[fl.Lattice | fl.Expression] = []

        input_str: str = "Why "

        t0 = time.perf_counter()
        index = fl.Lattice(input_str, vocabulary, ac_base)
        t1 = time.perf_counter()

        indexes.append(index)

        print(f"Lattice '{input_str}' created ({(t1 - t0) * 1000:.2f} ms), memory usage: {index.memory_usage()} bytes")

        input_str = "monday|tuesday|wednesday|thursday|friday"

        t0 = time.perf_counter()
        index = fl.Expression(input_str, vocabulary, toktrie_base)
        t1 = time.perf_counter()

        indexes.append(index)

        print(f"Expression '{input_str}' created ({(t1 - t0) * 1000:.2f} ms), memory usage: {index.memory_usage()} bytes")

        input_str = "?"

        t0 = time.perf_counter()
        index = fl.Lattice(input_str, vocabulary, ac_base)
        t1 = time.perf_counter()

        indexes.append(index)

        print(f"Lattice '{input_str}' created ({(t1 - t0) * 1000:.2f} ms), memory usage: {index.memory_usage()} bytes")

        current: str = ""
        eos_id: int = vocabulary.get_eos_id()

        for index in indexes:
            print(f"Number of nodes: {index.node_count()}")

            current_node: int = 0

            while True:
                transitions: NDArray[np.uint64] = index.transitions(current_node)

                if transitions.size == 0:
                    break

                if eos_id in transitions:
                    break

                routes: list[str] = []

                for token_id in transitions:
                    token: str | None = vocabulary.get_token_by_id(int(token_id))

                    if token:
                        routes.append(f"`{token}`")

                print("Routes:", " ".join(routes))

                selected_token_id: int | None = None

                while selected_token_id is None:
                    try:
                        input_str = input("> ").rstrip("\n")

                        if not input_str:
                            print("Empty input")

                            continue

                        token_id_from_input: int | None = vocabulary.get_id_by_token(input_str)

                        if token_id_from_input is not None and token_id_from_input in transitions:
                            selected_token_id = token_id_from_input
                        else:
                            print("Invalid or non-existent token!")

                    except EOFError:
                        print("\nExiting")

                        return

                    except Exception as e:
                        print(f"Error during input: {e}")

                        return

                selected_token: str | None = vocabulary.get_token_by_id(selected_token_id)

                if selected_token:
                    current += selected_token

                print("Current:", current)

                next_node: int | None = index.next(current_node, selected_token_id)

                if next_node is not None:
                    current_node = next_node
                else:
                    break

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
