"""Random walks through the syntax graph: `python -m tools.fuzz`.

A walk starts a fresh engine and types one character at a time, each picked
from the routes the engine offers, until the statement completes or the step
budget runs out. Everything it types was offered, so every walk tests the one
promise the engine makes - nothing it offers leads nowhere. A walk fails when

    rejected   a character the routes offered is refused by `feed`
    dead       nothing is offered, but the statement is not complete
    trapped    it ran out of steps where only whitespace can ever follow
    refused    it completed, and SQLite will not run the statement

A walk that runs out of steps is no failure by itself, since a condition can
be AND-ed onto forever, but it is checked for a trap: if nothing but
whitespace is offered, even after one more space, the statement can never be
finished. Every walk that completes is run in SQLite over the schema it was
written against, filled from `--data` where there is any. A statement that
runs out of time there is reported, not failed: a recursive definition may
never stop and a cross join of twenty tables may take forever, and both are
still SQL.

Two strategies pick the next character:

    words   mostly the rest of a word some lattice head is spelling, picked
            uniformly among them, so `HAVING` is as likely as a column name;
            otherwise one character, the way `chars` picks it
    chars   one character, weighted towards what lattice heads spell next
            and towards the brackets, quotes and terminator that close things

Completed statements are written to `--out`, `out/fuzz/<schema>.jsonl` unless
said otherwise, one JSON string per line, which is what `tools/postgres.py`
reads. The exit status is the number of failed
walks, capped like the test suite's.

    python -m tools.fuzz
    python -m tools.fuzz --schema tools/schemas/harsh.sql --walks 2000
    python -m tools.fuzz --strategy chars --seed 7 --threads 4
"""

from __future__ import annotations

import argparse
import json
import random
import string
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

HERE: Path = Path(__file__).resolve().parent
SEER: Path = HERE.parent

if str(SEER) not in sys.path:
    sys.path.insert(0, str(SEER))

from src import DraftKind, Engine, Schema, parse_schema  # noqa: E402
from test.database import Database, Execution  # noqa: E402
from test.feeder import Feeder  # noqa: E402
from test.report import Bar  # noqa: E402

# The corpus's schema and rows are the defaults, so a plain run walks what
# the suite tests.
VOCABULARY_PATH: Path = SEER.parent / "vocabulary.tiktoken"
SCHEMA_PATH: Path = SEER / "test" / "schema.sql"
DATA_PATH: Path = SEER / "test" / "data.sql"
OUT: Path = SEER / "out" / "fuzz"

# As in the test suite: the shell truncates a status to a byte.
MAX_STATUS: int = 125

# Every character a walk may type: printable ASCII, and the whitespace SQL
# separates words with.
ALPHABET: str = "".join(c for c in string.printable if c not in "\r\x0b\x0c")

# How likely a word walk is to spell out the rest of a lattice word rather
# than type a single character.
WORD_RATE: float = 0.8

COMPLETED: str = "completed"
LONG: str = "long"
FAILURES: tuple[str, ...] = ("rejected", "dead", "trapped", "refused")

@dataclass(frozen=True)
class Walk:
    """What one walk typed and how it ended."""

    text: str
    state: str
    """`completed`, `long`, or one of the `FAILURES`."""

    detail: str = ""

    @property
    def failed(self) -> bool:
        return self.state in FAILURES

class Walker:
    """Random walks over one schema, sharing the indexes between them."""

    __slots__ = ("_feeder", "_rng", "_strategy", "_steps", "_ids", "_characters")

    def __init__(self, feeder: Feeder, seed: int, strategy: str, steps: int) -> None:
        self._feeder = feeder
        self._rng = random.Random(seed)
        self._strategy = strategy
        self._steps = steps

        # Every character the vocabulary spells as a token of its own. Any
        # route has a first character, so asking which of these the engine
        # offers is enough to know what it offers at all.
        spelled: dict[str, int] = {}

        for character in ALPHABET:
            token_id: int | None = feeder.token_id(character)

            if token_id is not None:
                spelled[character] = token_id

        self._ids: NDArray[np.uint64] = np.array(list(spelled.values()), dtype=np.uint64)
        self._characters: tuple[str, ...] = tuple(spelled)

    def _offered(self, engine: Engine) -> list[str]:
        """The characters the engine offers next, in a stable order."""

        mask: NDArray[np.bool_] = np.isin(self._ids, engine.routes())

        return [character for character, offered in zip(self._characters, mask) if offered]

    @staticmethod
    def _words(engine: Engine) -> list[str]:
        """What is left of every word a lattice head is spelling, sorted."""

        words: set[str] = set()

        for head in engine.heads:
            draft = head.payload.draft

            if draft.kind is DraftKind.LATTICE and len(draft.value) > len(head.matched):
                words.add(draft.value[len(head.matched):])

        return sorted(words)

    def _character(self, engine: Engine, offered: list[str], text: list[str]) -> str:
        """One character, weighted so that walks stay short and close what they open."""

        nexts: set[str] = {word[0] for word in self._words(engine)} if self._strategy == "chars" else set()

        run: int = 0

        for character in reversed(text):
            if not (character.isalnum() or character == "_"):
                break

            run += 1

        weights: list[float] = []

        for character in offered:
            if character in nexts:
                weight: float = 10.0
            elif character == ";":
                weight = 1.0 + len(text) / 20
            elif character in ")'":
                weight = 4.0
            elif character == " ":
                weight = 2.0
            elif character.isspace():
                weight = 0.05
            elif character.isalnum() or character == "_":
                # Names are invented one character at a time, so without this
                # one could grow for the whole of the step budget.
                weight = 1.0 if run < 2 else 0.1
            else:
                weight = 0.5

            weights.append(weight)

        return self._rng.choices(offered, weights)[0]

    def walk(self) -> tuple[Walk, Engine]:
        """One walk, and the engine where it stopped."""

        engine: Engine = self._feeder.engine()
        text: list[str] = []

        while len(text) < self._steps:
            if engine.is_completed():
                return Walk("".join(text), COMPLETED), engine

            offered: list[str] = self._offered(engine)

            if not offered:
                return Walk("".join(text), "dead", "nothing is offered"), engine

            words: list[str] = self._words(engine) if self._strategy == "words" else []

            if words and self._rng.random() < WORD_RATE:
                chunk: str = self._rng.choice(words)
            else:
                chunk = self._character(engine, offered, text)

            for character in chunk:
                token_id: int | None = self._feeder.token_id(character)

                # The other heads may have moved on from what the chosen one
                # still spells; the walk goes on from wherever that leaves it.
                if token_id is None or token_id not in engine.routes():
                    break

                if not engine.feed(token_id):
                    return Walk("".join(text) + character, "rejected", f"{character!r} was offered"), engine

                text.append(character)

        if engine.is_completed():
            return Walk("".join(text), COMPLETED), engine

        return Walk("".join(text), LONG), engine

    def is_trapped(self, engine: Engine) -> bool:
        """Whether only whitespace can ever follow, even after one more space."""

        offered: list[str] = self._offered(engine)

        if any(not character.isspace() for character in offered):
            return False

        token_id: int | None = self._feeder.token_id(" ")

        if token_id is None or " " not in offered or not engine.feed(token_id):
            return True

        return all(character.isspace() for character in self._offered(engine))

def judge(walker: Walker, database: Database) -> tuple[Walk, Execution | None]:
    walk, engine = walker.walk()

    if walk.state == LONG and walker.is_trapped(engine):
        return Walk(walk.text, "trapped", "only whitespace follows"), None

    if walk.state != COMPLETED:
        return walk, None

    execution: Execution = database.run(walk.text)

    if execution.succeeded or is_timeout(execution):
        return walk, execution

    return Walk(walk.text, "refused", f"SQLite: {execution.error}"), execution

def is_timeout(execution: Execution) -> bool:
    return execution.error is not None and execution.error.startswith("did not finish")

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m tools.fuzz",
        description="Walk the syntax graph at random and check that nothing it offers leads nowhere.",
    )

    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    parser.add_argument("--data", type=Path, default=None, help="rows for SQLite; the corpus's for its schema")
    parser.add_argument("--vocabulary", type=Path, default=VOCABULARY_PATH)
    parser.add_argument("--walks", type=int, default=500)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--strategy", choices=("words", "chars"), default="words")
    parser.add_argument("--steps", type=int, default=900, help="characters a walk may type")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--budget", type=float, default=2.0, help="seconds a statement may run in SQLite")
    parser.add_argument("--out", type=Path, default=None, help="where completed statements are written")

    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    args: argparse.Namespace = parse_args(argv)

    data: Path | None = args.data

    if data is None and args.schema.resolve() == SCHEMA_PATH:
        data = DATA_PATH

    try:
        text: str = args.schema.read_text(encoding="utf-8")
        schema: Schema | None = parse_schema(text)

        if schema is None:
            raise RuntimeError(f"Failed to parse {args.schema}")

        database: Database = Database(text, "" if data is None else data.read_text(encoding="utf-8"), args.budget)
        feeder: Feeder = Feeder(args.vocabulary, schema, args.threads)
    except (OSError, RuntimeError) as error:
        print(f"Failed to start: {error}", file=sys.stderr)

        return MAX_STATUS

    walker: Walker = Walker(feeder, args.seed, args.strategy, args.steps)
    out_path: Path = args.out if args.out is not None else OUT / f"{args.schema.stem}.jsonl"
    states: dict[str, int] = {}
    timeouts: int = 0
    started: float = time.monotonic()

    out_path.parent.mkdir(parents=True, exist_ok=True)

    bar: Bar = Bar(args.walks)

    with open(out_path, "w", encoding="utf-8") as out:
        for _ in range(args.walks):
            bar.draw(args.schema.name)

            walk, execution = judge(walker, database)

            states[walk.state] = states.get(walk.state, 0) + 1
            timeouts += execution is not None and is_timeout(execution)

            if walk.state == COMPLETED:
                out.write(json.dumps(walk.text) + "\n")

            bar.record(not walk.failed)

            if walk.failed:
                bar.clear()

                print(f"  {walk.state.upper():8s}  {walk.text!r}")
                print(f"            {walk.detail}")

    bar.clear()
    database.close()

    failed: int = sum(states.get(state, 0) for state in FAILURES)

    print(
        f"\n{args.walks} walks over {args.schema.name} in {time.monotonic() - started:.1f}s: "
        f"{states.get(COMPLETED, 0)} completed ({timeouts} out of time in SQLite), "
        f"{states.get(LONG, 0)} out of steps, {failed} failed"
    )

    return min(failed, MAX_STATUS)

if __name__ == "__main__":
    raise SystemExit(main())
