"""The run, end to end: `python -m test`.

Every record of the corpus is fed into the engine one character at a time
(`feeder.py`), and has to end the way it declares. Every legal record that
does is then run in SQLite (`database.py`), and has to run. A record fails for
either, and the report says which.

The engine generates over `schema.sql` and the database is built from the
same file, so the two cannot disagree about what exists; `data.sql` fills it.

The exit status is the number of records that misbehaved, capped at 125, so
`make test` fails the build when any of them does.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

HERE: Path = Path(__file__).resolve().parent
SEER: Path = HERE.parent

if str(SEER) not in sys.path:
    sys.path.insert(0, str(SEER))

from src import Schema, parse_schema  # noqa: E402

from .corpus import Record, read_records  # noqa: E402
from .database import Database, Execution  # noqa: E402
from .feeder import Feeder, Outcome  # noqa: E402
from .report import Bar  # noqa: E402

VOCABULARY_PATH: Path = SEER.parent / "vocabulary.tiktoken"
SCHEMA_PATH: Path = HERE / "schema.sql"
DATA_PATH: Path = HERE / "data.sql"
QUERIES_PATH: Path = HERE / "cases.yaml"

# The shell truncates a status to a byte and treats the top of the range as a
# signal, so a run with more failures than this still reports the same defeat.
MAX_STATUS: int = 125

@dataclass(frozen=True)
class Verdict:
    """What one record came to: the feed, and the run where there was one."""

    outcome: Outcome
    execution: Execution | None = None

    def passed(self, record: Record) -> bool:
        if self.outcome.state != record.expect:
            return False

        return self.execution is None or self.execution.succeeded

    def explain(self, record: Record) -> str:
        if self.outcome.state != record.expect:
            return f"expected {record.expect}, {self.outcome.describe(record.query)}"

        assert self.execution is not None and self.execution.error is not None

        return f"completed, but SQLite refused it: {self.execution.error}"

def judge(record: Record, feeder: Feeder, database: Database | None) -> Verdict:
    """Feed `record`, and run it where it is legal and completed."""

    outcome: Outcome = feeder.feed(record.query)

    # The declared outcome *is* the first test: a legal query has to complete
    # and an illegal one has to get stuck. Only a legal query that completed
    # is SQL the engine stands behind, so only that one is run.
    if database is None or not record.is_legal or not outcome.completed:
        return Verdict(outcome)

    return Verdict(outcome, database.run(record.query))

@dataclass
class Tally:
    failed: list[Record]
    ran: int = 0
    empty: int = 0

def run(records: list[Record], feeder: Feeder, database: Database | None, verbose: bool = False) -> Tally:
    """Judge every record, reporting as it goes."""

    tally: Tally = Tally([])
    heading: str = ""

    bar: Bar = Bar(len(records))

    for record in records:
        bar.draw(record.group)

        verdict: Verdict = judge(record, feeder, database)
        passed: bool = verdict.passed(record)

        if not passed:
            tally.failed.append(record)

        if verdict.execution is not None and verdict.execution.succeeded:
            tally.ran += 1
            tally.empty += verdict.execution.rows == 0

        bar.record(passed)

        if not verbose and passed:
            continue

        # Take the bar's line back before writing above it.
        bar.clear()

        # The group is printed once, above the first of its records that is
        # being shown, so the report keeps the file's own shape.
        if record.group != heading:
            heading = record.group

            print(f"\n{heading}")

        print(f"  {'ok  ' if passed else 'FAIL'}  {record.query!r}")

        if not passed:
            print(f"        {verdict.explain(record)}")

    bar.clear()

    return tally

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m test",
        description="Feed every query of the corpus into the engine, and run the legal ones in SQLite.",
    )

    parser.add_argument("--queries", type=Path, default=QUERIES_PATH)
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--vocabulary", type=Path, default=VOCABULARY_PATH)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--budget", type=float, default=2.0, help="seconds a query may run in SQLite")
    parser.add_argument("--no-database", action="store_true", help="feed the corpus only")
    parser.add_argument("-v", "--verbose", action="store_true", help="print every record")

    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    args: argparse.Namespace = parse_args(argv)

    try:
        records: list[Record] = read_records(args.queries)
        text: str = args.schema.read_text(encoding="utf-8")
        schema: Schema | None = parse_schema(text)

        if schema is None:
            raise RuntimeError(f"Failed to parse {args.schema}")

        feeder: Feeder = Feeder(args.vocabulary, schema, args.threads)
        database: Database | None = None

        if not args.no_database:
            database = Database(text, args.data.read_text(encoding="utf-8"), args.budget)
    except (OSError, RuntimeError) as error:
        print(f"Failed to start: {error}", file=sys.stderr)

        return MAX_STATUS

    tally: Tally = run(records, feeder, database, args.verbose)

    legal: int = sum(1 for record in records if record.is_legal)

    print(
        f"\n{len(records) - len(tally.failed)}/{len(records)} records behaved as declared "
        f"({legal} legal, {len(records) - legal} illegal)"
    )

    if database is not None:
        print(f"{tally.ran}/{legal} legal records ran in SQLite ({tally.empty} returned no rows)")

        database.close()

    return min(len(tally.failed), MAX_STATUS)

if __name__ == "__main__":
    raise SystemExit(main())
