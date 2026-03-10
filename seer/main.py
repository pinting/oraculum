from llama_cpp import Llama, LogitsProcessorList

from core import set_schema, get_schema, VOCABULARY_PATH, EOS_ID, init_engine
from vocabulary import serialize_vocabulary
from processor import LogitsProcessor

set_schema("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    total DECIMAL(10, 2),
    status TEXT DEFAULT 'pending'
);
""")

PROMPT = "Generate an SQL SELECT request to get the emails of users!"

def main() -> None:
    model_path: str = "../models/gemma-3-4b-it-Q8_0.gguf"

    print(f"Loading model from {model_path}...")

    model: Llama = Llama(
        model_path=model_path,
        n_ctx=4096,
        n_threads=4,
        n_gpu_layers=999,
        verbose=False,
    )

    print("Model loaded successfully!")

    raw_vocabulary: str = serialize_vocabulary(model)
    raw_vocabulary_bytes: bytes = raw_vocabulary.encode("utf-8")

    init_engine(raw_vocabulary_bytes, EOS_ID, get_schema())

    with open(VOCABULARY_PATH, "w", encoding="utf-8") as f:
        f.write(raw_vocabulary)

    print("Vocabulary saved successfully!")

    vocab_size: int = model.n_vocab()
    processor: LogitsProcessor = LogitsProcessor(vocab_size)

    prompt: str = f"{get_schema()}\n\n{PROMPT}"
    prompt_tokens: list[int] = model.tokenize(prompt.encode("utf-8"))

    print("Generating response...\n")

    for token_id in model.generate(
        prompt_tokens,
        top_p=0.9,
        temp=0.7,
        logits_processor=LogitsProcessorList([processor]),
    ):
        token: bytes = model.detokenize([token_id])

        print(token_id, token)

        if len(token) == 0:
            break

        result: int = processor.feed(token_id)

        if result != 0:
            break

if __name__ == "__main__":
    main()
