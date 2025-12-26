from typing import Any
from llama_cpp import Llama, LogitsProcessorList

from vocabulary import serialize_vocabulary
from processor import LogitsProcessor

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

    with open(vocabulary_path, 'w', encoding='utf-8') as f:
        f.write(raw_vocabulary)

    print(f"Vocabulary exported successfully!")

    processor: LogitsProcessor = LogitsProcessor()
    logits_processor: LogitsProcessorList = LogitsProcessorList([processor])

    prompt: str = "Hello, how are you?"

    print("Generating response...\n")

    stream: Any = model(
        prompt,
        max_tokens=100,
        temperature=0.7,
        top_p=0.9,
        logits_processor=logits_processor,
        echo=False,
        stream=True
    )
    
    for chunk in stream:
        if chunk['choices'][0]['text']:
            text: str = chunk['choices'][0]['text']

            print(text, end="", flush=True)

if __name__ == "__main__":
    main()
