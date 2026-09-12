"""Interactive driver -- the first of the two entry points.

Loads the vocabulary from disk, builds the engine over a schema and walks the
syntax graph one token at a time, printing the tokens the graph currently
allows and reading the next one from stdin.

    python main.py                    # one kernel worker
    python main.py --threads 8        # eight
    python main.py --schema my.sql

See `live.py` for the model driven entry point.
"""

from __future__ import annotations

import argparse
import sys

import core
from core import EOS_ID, VOCABULARY_PATH, SCHEMA
from src import Engine, debug

ROUTE_LIMIT: int = 100

def printable(token: str) -> bool:
    """Mirror the display filter of `main.rs`."""

    if len(token) != 1 and token.isspace():
        return False

    return not any(ord(c) < 32 or ord(c) == 127 for c in token)

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Walk the seer SQL syntax graph interactively.")

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

    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    args: argparse.Namespace = parse_args(argv)

    if args.debug:
        debug.enable()

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
            shown: list[str] = routes[:ROUTE_LIMIT]

            print(
                "Routes: "
                + ", ".join(f"`{token}`" for token in shown)
                + (", ..." if len(switch) > len(shown) else " ")
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

if __name__ == "__main__":
    raise SystemExit(main())
