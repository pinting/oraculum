"""The whole test suite: feed every query of the corpus into the engine, one character at a time.

The engine is a generator, not a parser, so there is nothing to call on a
finished string - the only question it answers is which tokens may come next.
Feeding a query character by character turns that into a yes/no test, because a
single character is either among the routes the graph is offering or it is not:

* if it is, the engine takes it and the next character is asked about;
* if it is not, the feed is **stuck** - the graph never offered that character,
  so the text is outside the subset of SQL seer implements.

So a feed has exactly two outcomes, and a record declares which one it wants.
`expect: completed` means the feed has to walk the whole string and find the
statement completed at EOF; `expect: stuck` means it has to stop somewhere
before that. Reaching EOF with the statement unfinished counts as stuck too -
the graph is still waiting for more, so the string was not a statement.

The corpus is `cases.yaml`, a list of groups. A group names one idea, carries
the `expect` that idea asserts and the queries it asserts it over, so the
expectation is written once per idea rather than once per query and a failure
can say which idea broke.

Every single character of the query has to be a token of its own, which the
Gemma vocabulary does supply for the whole of printable ASCII. A character it
does not spell is reported as a broken record rather than as a failure of the
engine.

    python tests/main.py
    python tests/main.py --verbose
    python tests/main.py --queries other.yaml --schema other.sql

The exit status is the number of records that misbehaved, capped at 125, so
`make test` fails the build when any of them does.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml

import kernel as kl

from src.engine import Engine
from src.factory import IndexFactory
from src.graph import root
from src.schema import Schema, parse_schema

VOCABULARY_PATH: Path = ROOT.parent / "vocabulary.tiktoken"
SCHEMA_PATH: Path = ROOT / "schema.sql"
QUERIES_PATH: Path = Path(__file__).resolve().parent / "cases.yaml"

EOS_ID: int = 1

# The two outcomes a feed has, and the two words `expect` may be written with.
COMPLETED: str = "completed"
STUCK: str = "stuck"

EXPECTATIONS: frozenset[str] = frozenset({COMPLETED, STUCK})

# The shell truncates a status to a byte and treats the top of the range as a
# signal, so a run with more failures than this still reports the same defeat.
MAX_STATUS: int = 125

@dataclass(frozen=True)
class Record:
    """One query, with the group it was declared in for the report."""

    group: str
    query: str
    expect: str
    """`COMPLETED` or `STUCK` - what feeding the query has to end in."""

@dataclass(frozen=True)
class Outcome:
    """What happened when the record's query was fed in.

    `consumed` is how many characters the engine took before it stopped, so a
    stuck feed points at exactly the character the graph refused.
    """

    completed: bool
    consumed: int
    reason: str

    @property
    def state(self) -> str:
        """The outcome as a record spells it, which is what the test compares."""

        return COMPLETED if self.completed else STUCK

def describe(record: Record, outcome: Outcome) -> str:
    """Where a stuck feed stopped, as the text taken and the character refused."""

    taken: str = record.query[: outcome.consumed]
    rest: str = record.query[outcome.consumed :]

    return f"took {taken!r}, then {outcome.reason} at {rest[:1]!r}"

class Feeder:
    """A vocabulary and a schema, reusable across queries.

    Loading the vocabulary and building the Aho-Corasick and TokTrie bases over
    it costs about half a second, and the factory memoises every index it
    builds, so both are made once and every query gets a fresh `Engine` over
    them. The engine holds all the per-query state; nothing leaks between runs.
    """

    def __init__(
        self,
        vocabulary_path: Path = VOCABULARY_PATH,
        schema_path: Path = SCHEMA_PATH,
        threads: int = 1,
    ) -> None:
        self.vocabulary: kl.Vocabulary = kl.Vocabulary.from_file_path(
            str(vocabulary_path), EOS_ID
        )

        parsed: Schema | None = parse_schema(schema_path.read_text(encoding="utf-8"))

        if parsed is None:
            raise RuntimeError(f"Failed to parse {schema_path}")

        self.schema: Schema = parsed
        self.factory: IndexFactory = IndexFactory(self.vocabulary)
        self.threads: int = threads

        # One id per character, resolved once. `None` marks a character the
        # vocabulary cannot spell alone, which makes the record unfeedable
        # rather than illegal.
        self._ids: dict[str, int | None] = {}

    def token_id(self, character: str) -> int | None:
        if character not in self._ids:
            self._ids[character] = self.vocabulary.get_id_by_token(character)

        return self._ids[character]

    def feed(self, query: str) -> Outcome:
        """Walk `query` one character at a time through a fresh engine."""

        engine: Engine = Engine(
            self.vocabulary,
            self.schema,
            root(),
            factory=self.factory,
            threads=self.threads,
        )

        for consumed, character in enumerate(query):
            token_id: int | None = self.token_id(character)

            if token_id is None:
                return Outcome(False, consumed, "the vocabulary cannot spell")

            # A completed statement has no routes left, so a character after
            # the terminator is refused here rather than by `feed`.
            if token_id not in engine.routes():
                return Outcome(False, consumed, "no route offered")

            if not engine.feed(token_id):
                return Outcome(False, consumed, "no head accepted")

        if not engine.is_completed():
            return Outcome(False, len(query), "EOF with the statement unfinished")

        return Outcome(True, len(query), "completed")

def read_records(path: Path = QUERIES_PATH) -> list[Record]:
    """The corpus, flattened.

    The file is a list of groups, each naming one idea, carrying the `expect`
    that idea asserts and the queries it asserts it over. Every query comes
    back tagged with its group, so a failure says which idea broke.
    """

    with open(path, "r", encoding="utf-8") as handle:
        groups: object = yaml.safe_load(handle)

    if not isinstance(groups, list):
        raise RuntimeError(f"{path}: expected a list of groups")

    records: list[Record] = []

    for position, group in enumerate(groups, start=1):
        if not isinstance(group, dict):
            raise RuntimeError(f"{path}: group {position} is not a mapping")

        missing: set[str] = {"group", "expect", "queries"} - set(group)

        if missing:
            raise RuntimeError(f"{path}: group {position} is missing {sorted(missing)}")

        name: str = str(group["group"])
        expect: object = group["expect"]

        if expect not in EXPECTATIONS:
            raise RuntimeError(
                f"{path}: {name!r} expects {expect!r}, not {COMPLETED!r} or {STUCK!r}"
            )

        queries: object = group["queries"]

        if not isinstance(queries, list) or not all(isinstance(q, str) for q in queries):
            raise RuntimeError(f"{path}: {name!r} does not hold a list of queries")

        records.extend(Record(name, query, str(expect)) for query in queries)

    return records

def run(records: list[Record], feeder: Feeder, verbose: bool = False) -> list[Record]:
    """Feed every record, reporting as it goes. Returns the ones that misbehaved."""

    failed: list[Record] = []
    heading: str = ""

    for record in records:
        outcome: Outcome = feeder.feed(record.query)

        # The declared outcome *is* the test: a legal query has to complete and
        # an illegal one has to get stuck.
        passed: bool = outcome.state == record.expect

        if not passed:
            failed.append(record)

        if not verbose and passed:
            continue

        # The group is printed once, above the first of its records that is
        # being shown, so the report keeps the file's own shape.
        if record.group != heading:
            heading = record.group

            print(f"\n{heading}")

        print(f"  {'ok  ' if passed else 'FAIL'}  {record.query!r}")

        if not passed:
            print(f"        expected {record.expect}, {describe(record, outcome)}")

    return failed

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Feed every query of the corpus into the engine, character by character.",
    )

    parser.add_argument("--queries", type=Path, default=QUERIES_PATH)
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    parser.add_argument("--vocabulary", type=Path, default=VOCABULARY_PATH)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("-v", "--verbose", action="store_true", help="print every record")

    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    args: argparse.Namespace = parse_args(argv)

    try:
        records: list[Record] = read_records(args.queries)
        feeder: Feeder = Feeder(args.vocabulary, args.schema, args.threads)
    except (OSError, RuntimeError) as error:
        print(f"Failed to start: {error}", file=sys.stderr)

        return MAX_STATUS

    failed: list[Record] = run(records, feeder, args.verbose)

    legal: int = sum(1 for record in records if record.expect == COMPLETED)

    print(
        f"\n{len(records) - len(failed)}/{len(records)} records behaved as declared "
        f"({legal} legal, {len(records) - legal} illegal)"
    )

    return min(len(failed), MAX_STATUS)

if __name__ == "__main__":
    raise SystemExit(main())
