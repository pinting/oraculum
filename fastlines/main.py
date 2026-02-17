from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
import sys

import fastlines_typed as fl

def main() -> None:
    try:
        try:
            vocabulary: fl.Vocabulary = fl.Vocabulary.from_file_path("../vocabulary.tiktoken", 1, 32)

        except Exception:
            print("Error: vocabulary.tiktoken file not found or failed to load.")

            return

        print("Vocabulary loaded")

        ac_base: fl.AhoCorasick = fl.AhoCorasick(vocabulary, fl.AC_CONTIGUOUS_NFA)

        print("Lattice base (AhoCorasick) built")

        toktrie_base: fl.TokTrie = fl.TokTrie(vocabulary, fl.FAST_HASH_DFA, 32, 32, 32)

        print("Expression base (TokTrie) built with FastHashDFA<32, 32, 32> config")

        indexes: list[fl.Lattice | fl.Expression] = []
        input_str: str = "Why "

        indexes.append(fl.Lattice(input_str, vocabulary, ac_base))

        print(f"Lattice '{input_str}' created")

        input_str = "monday|tuesday|wednesday|thursday|friday"

        indexes.append(fl.Expression(input_str, vocabulary, toktrie_base))

        print(f"Expression '{input_str}' created")

        input_str = "?"

        indexes.append(fl.Lattice(input_str, vocabulary, ac_base))

        print(f"Lattice '{input_str}' created")

        current: str = ""
        eos_id: int = vocabulary.get_eos_id()
        current_index_idx: int = 0

        while current_index_idx < len(indexes):
            idx_obj: fl.Lattice | fl.Expression = indexes[current_index_idx]
            current_node: int = idx_obj.start()

            while True:
                transitions: NDArray[np.uint64] = idx_obj.transitions(current_node)

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

                next_node: int | None = idx_obj.next(current_node, selected_token_id)

                if next_node is not None:
                    current_node = next_node
                else:
                    break

            current_index_idx += 1

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
