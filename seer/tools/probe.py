"""What the syntax graph offers after a prefix: `python -m tools.probe`.

Each prefix is fed into a fresh engine one character at a time, the way the
test suite feeds a query, and the routes the engine offers at the end are
printed: the tokens that are not whitespace, shortest first, and whether
whitespace is offered besides. It is the quickest way to see why a walk of
`tools.fuzz` stopped where it did, or what a clause opens onto.

    python -m tools.probe "SELECT email FROM users WHERE "
    python -m tools.probe --schema tools/schemas/harsh.sql "SELECT a FROM flags ORDER BY a, b, "
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE: Path = Path(__file__).resolve().parent
SEER: Path = HERE.parent

if str(SEER) not in sys.path:
    sys.path.insert(0, str(SEER))

from src import Engine, Schema, parse_schema  # noqa: E402
from test.feeder import Feeder  # noqa: E402

VOCABULARY_PATH: Path = SEER.parent / "vocabulary.tiktoken"
SCHEMA_PATH: Path = SEER / "test" / "schema.sql"

def probe(feeder: Feeder, prefix: str, limit: int) -> str:
    """One report: where the feed stopped, and what is offered there."""

    engine: Engine = feeder.engine()

    for consumed, character in enumerate(prefix):
        token_id: int | None = feeder.token_id(character)

        if token_id is None or token_id not in engine.routes() or not engine.feed(token_id):
            return f"stuck after {prefix[:consumed]!r}: {character!r} is not offered"

    if engine.is_completed():
        return "completed"

    tokens: set[str] = set()

    for route in engine.routes().tolist():
        token: str | None = feeder.vocabulary.get_token_by_id(route)

        if token:
            tokens.add(token)

    words: list[str] = sorted((token for token in tokens if not token.isspace()), key=lambda t: (len(t), t))
    spaces: str = ", and whitespace" if any(token.isspace() for token in tokens) else ""
    shown: str = ", ".join(repr(word) for word in words[:limit])
    more: str = f", ... {len(words) - limit} more" if len(words) > limit else ""

    return f"{len(engine)} heads, {len(tokens)} routes: {shown}{more}{spaces}"

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.probe",
        description="Feed each prefix into a fresh engine and print what it offers next.",
    )

    parser.add_argument("prefixes", nargs="+")
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    parser.add_argument("--vocabulary", type=Path, default=VOCABULARY_PATH)
    parser.add_argument("--limit", type=int, default=30, help="routes shown per prefix")

    args: argparse.Namespace = parser.parse_args(argv)

    try:
        schema: Schema | None = parse_schema(args.schema.read_text(encoding="utf-8"))

        if schema is None:
            raise RuntimeError(f"Failed to parse {args.schema}")

        feeder: Feeder = Feeder(args.vocabulary, schema)
    except (OSError, RuntimeError) as error:
        print(f"Failed to start: {error}", file=sys.stderr)

        return 1

    for prefix in args.prefixes:
        print(f"{prefix!r}\n    {probe(feeder, prefix, args.limit)}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
