from typing import Any

from llama_cpp import Llama, LogitsProcessorList

from vocabulary import serialize_vocabulary
from processor import LogitsProcessor
import oraculum

SCHEMA: str = """
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
"""

def main() -> None:
    model_path: str = "./models/gemma-3-4b-it-Q8_0.gguf"
    vocabulary_path: str = "./vocabulary.tiktoken"

    print(f"Loading model from {model_path}...")

    model: Llama = Llama(
        model_path=model_path,
        n_ctx=4096,
        n_threads=4,
        n_gpu_layers=999,
        verbose=False
    )

    print("Model loaded successfully!")

    raw_vocabulary: str = serialize_vocabulary(model)
    raw_vocabulary_bytes: bytes = raw_vocabulary.encode('utf-8')

    result: int = oraculum.init_vocabulary(raw_vocabulary_bytes)

    if result != 0:
        print("Failed to initialize vocabulary!")

        return

    print("Vocabulary initialized successfully!")

    with open(vocabulary_path, 'w', encoding='utf-8') as f:
        f.write(raw_vocabulary)

    print(f"Vocabulary saved successfully!")

    schema: bytes = SCHEMA.encode('utf-8')
    result = oraculum.init_schema(schema)

    if result != 0:
        print("Failed to initialize schema!")

        return

    print("Schema initialized successfully!")

    vocab_size: int = model.n_vocab()

    processor: LogitsProcessor = LogitsProcessor(vocab_size)
    logits_processor: LogitsProcessorList = LogitsProcessorList([processor])

    prompt: str = "Hello, how are you?"
    prompt_tokens: list[int] = model.tokenize(prompt.encode('utf-8'))

    print("Generating response...\n")

    for token_id in model.generate(
        prompt_tokens,
        top_p=0.9,
        temp=0.7,
        logits_processor=logits_processor
    ):
        processor.feed_token(token_id)

        text: str = model.detokenize([token_id]).decode('utf-8', errors='ignore')

        # Disabled for now as the engine prints everything to stdout
        # print(text, end='', flush=True)

if __name__ == "__main__":
    main()
