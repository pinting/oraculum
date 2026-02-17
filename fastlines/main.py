import fastlines
import sys

def main():
    try:
        try:
            with open("../vocabulary.tiktoken", "rb") as f:
                vocab_data = f.read()
        
        except FileNotFoundError:
            print("Error: vocabulary.tiktoken file not found.")
            return

        # Assuming EOS token ID is 1
        vocabulary = fastlines.Vocabulary(vocab_data, 1)

        print("Vocabulary loaded.")

        lattice_base = fastlines.AhoCorasick.new(vocabulary, 0)
        
        print("Lattice base (AhoCorasick) built.")

        expression_base = fastlines.TokTrie.new(vocabulary)

        print("Expression base (TokTrie) built.")

        indexes = []

        input_str = "John is having a busy "

        indexes.append(fastlines.Lattice(input_str, vocabulary, lattice_base))

        print(f"Lattice '{input_str}' created.")

        input_str = "monday|tuesday|wednesday|thursday|friday"

        indexes.append(fastlines.Expression(input_str, vocabulary, expression_base))

        print(f"Expression '{input_str}' created.")

        input_str = " this week!"

        indexes.append(fastlines.Lattice(input_str, vocabulary, lattice_base))

        print(f"Lattice '{input_str}' created.")

        current = ""
        eos_id = vocabulary.get_eos_id()
        current_index_idx = 0

        while current_index_idx < len(indexes):
            idx_obj = indexes[current_index_idx]
            current_node = idx_obj.start()

            while True:
                transitions = idx_obj.transitions(current_node)
                
                if transitions.size == 0:
                    break
                
                if eos_id in transitions:
                    break

                routes = []

                for token_id in transitions:
                    token = vocabulary.get_token_by_id(int(token_id))
                    if token:
                        routes.append(f"`{token}`")
                
                print("Routes:", " ".join(routes))

                selected_token_id = None

                while selected_token_id is None:
                    try:
                        input_str = input("> ").rstrip('\n')

                        if not input_str:
                            print("Empty input")

                            continue

                        token_id_from_input = vocabulary.get_id_by_token(input_str)

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

                selected_token = vocabulary.get_token_by_id(selected_token_id)

                if selected_token:
                    current += selected_token
                
                print("Current:", current)

                next_node = idx_obj.next(current_node, selected_token_id)

                if next_node is not None:
                    current_node = next_node
                else:
                    break
            
            current_index_idx += 1

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()