"""Seer module entry point."""

from __future__ import annotations

import argparse
import sys

import core
from core import EOS_ID, SCHEMA, VOCABULARY_PATH, get_schema, init_engine, set_schema
from src import Engine, debug

ROUTE_LIMIT: int = 100

def printable(token: str) -> bool:
    """Mirror the display filter of `main.rs`."""
    if len(token) != 1 and token.isspace():
        return False
    return not any(ord(c) < 32 or ord(c) == 127 for c in token)

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Walk the seer SQL syntax graph interactively or with a model.")
    parser.add_argument("--live", action="store_true", help="run in model-driven live mode")

    parser.add_argument("--vocabulary", default=VOCABULARY_PATH, help="tiktoken vocabulary file")
    parser.add_argument("--eos-id", type=int, default=EOS_ID, help="end of sequence token id")
    parser.add_argument("--threads", type=int, default=1, help="kernel worker threads")
    parser.add_argument("--schema", default=None, help="path to a .sql schema, defaults to the built-in one")
    parser.add_argument(
        "--no-debug",
        dest="debug",
        action="store_false",
        help="do not print the resolver state after each modifying operation",
    )

    # Live mode arguments
    parser.add_argument("--model", default="../models/gemma-3-4b-it-Q8_0.gguf", help="path to the GGUF model")
    parser.add_argument("--model-threads", type=int, default=4, help="llama.cpp compute threads")
    parser.add_argument("--prompt", default="Generate an SQL SELECT request to get the emails of users!", help="instruction appended to the schema")
    parser.add_argument("--temp", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)

    return parser.parse_args(argv)

def run_interactive(args: argparse.Namespace) -> int:
    if args.schema is not None:
        with open(args.schema, "r", encoding="utf-8") as handle:
            core.set_schema(handle.read())
    else:
        core.set_schema(SCHEMA)

    try:
        raw_vocabulary: bytes = core.load_vocabulary(args.vocabulary)
    except OSError as error:
        print(f"Failed to load vocabulary: {error}", file=sys.stderr)
        return 1

    if args.threads > 1:
        print(f"Driving the head pool on {args.threads} kernel workers")

    try:
        engine: Engine = core.init_engine(
            raw_vocabulary,
            args.eos_id,
            core.get_schema(),
            args.threads,
        )
    except RuntimeError as error:
        print(f"Failed to initialize engine: {error}", file=sys.stderr)
        return 1

    try:
        while True:
            route_ids: list[int] = engine.routes().tolist()

            if not route_ids:
                break

            switch: dict[str, int] = {}

            for token_id in route_ids:
                token: str | None = engine.get_token(token_id)

                if token is not None:
                    switch[token] = token_id

            routes: list[str] = sorted(token for token in switch if printable(token))
            has_others = False

            if len(switch) > ROUTE_LIMIT:
                from src.factory import DraftKind
                constants = [
                    h.payload.draft.value[len(h.matched):] 
                    for h in engine.heads 
                    if h.payload.draft.kind == DraftKind.LATTICE
                ]
                constants = [c for c in constants if c]
                constants.extend([".", " ", "\t", ","])

                if constants:
                    constant_routes = []
                    for token in routes:
                        if any(c.startswith(token) for c in constants):
                            constant_routes.append(token)
                    
                    if constant_routes and len(constant_routes) < len(routes):
                        routes = constant_routes
                        has_others = True

            shown: list[str] = routes[:ROUTE_LIMIT]

            print(
                "Routes: "
                + ", ".join(f"`{token}`" for token in shown)
                + (", ..." if len(routes) > len(shown) or has_others else " ")
            )

            while True:
                try:
                    line: str = input("> ")
                except EOFError:
                    return 0

                if not line:
                    continue

                token_id = switch.get(line)

                if token_id is None:
                    print("Non-existent token!")
                    continue

                engine.feed(token_id)
                break

            print(f"Matched: `{engine.matched()}`")

            if engine.is_completed():
                break
    finally:
        core.shutdown()

    return 0

def run_live(args: argparse.Namespace) -> int:
    from processor import LogitsProcessor
    from vocabulary import serialize_vocabulary

    set_schema(SCHEMA)

    try:
        from llama_cpp import Llama, LogitsProcessorList
    except ImportError:
        print("llama-cpp-python is not installed; run `make model`", file=sys.stderr)
        return 1

    print(f"Loading model from {args.model}...")

    try:
        model = Llama(
            model_path=args.model,
            n_ctx=4096,
            n_threads=args.model_threads,
            n_gpu_layers=999,
            verbose=False,
        )
    except (OSError, ValueError) as error:
        print(f"Failed to load model: {error}", file=sys.stderr)
        return 1

    print("Model loaded successfully!")

    raw_vocabulary: str = serialize_vocabulary(model)
    raw_vocabulary_bytes: bytes = raw_vocabulary.encode("utf-8")

    if args.threads > 1:
        print(f"Driving the head pool on {args.threads} kernel workers")

    try:
        engine: Engine = init_engine(
            raw_vocabulary_bytes,
            args.eos_id,
            get_schema(),
            args.threads,
        )
    except RuntimeError as error:
        print(f"Failed to initialize engine: {error}", file=sys.stderr)
        return 1

    with open(args.vocabulary, "w", encoding="utf-8") as handle:
        handle.write(raw_vocabulary)

    print("Vocabulary saved successfully!")

    vocab_size: int = model.n_vocab()
    processor: LogitsProcessor = LogitsProcessor(vocab_size)

    prompt: str = f"{get_schema()}\n\n{args.prompt}"
    prompt_tokens: list[int] = model.tokenize(prompt.encode("utf-8"))

    print("Generating response...\n")

    try:
        for token_id in model.generate(
            prompt_tokens,
            top_p=args.top_p,
            temp=args.temp,
            logits_processor=LogitsProcessorList([processor]),
        ):
            token: bytes = model.detokenize([token_id])

            print(token_id, token)

            if len(token) == 0:
                break

            result: int = processor.feed(token_id)

            if result != 0:
                break

            # The Rust version has no equivalent: it relies on the route set
            # emptying out. Stopping here keeps the model from sampling past
            # the end of the statement.
            if processor.is_completed():
                break
    finally:
        core.shutdown()

    print(f"\nMatched: `{engine.matched()}`")

    return 0

def main(argv: list[str] | None = None) -> int:
    args: argparse.Namespace = parse_args(argv)

    if args.debug:
        debug.enable()

    if args.live:
        return run_live(args)
    else:
        return run_interactive(args)

if __name__ == "__main__":
    raise SystemExit(main())
