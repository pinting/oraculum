"""The run, end to end: `python -m test`.

Every record of the corpus is fed into the engine one character at a time
(`feeder.py`), and has to end the way it declares. Every legal record that
completes is then checked against every configured validator (`SQLiteValidator`
and `SqlglotValidator`). A record fails if the feed disagrees with the corpus
or if any validator rejects it.

The engine generates over `schema.sql` and every validator checks against the
same file, so they cannot disagree about what exists; `data.sql` fills SQLite.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE: Path = Path(__file__).resolve().parent
SEER: Path = HERE.parent

if str(SEER) not in sys.path:
    sys.path.insert(0, str(SEER))

from src import Schema, parse_schema  # noqa: E402

from .corpus import Record, read_records  # noqa: E402
from .feeder import Feeder, Outcome  # noqa: E402
from .report import Bar  # noqa: E402
from .validators import SQLiteValidator, SqlglotValidator, Validation, Validator  # noqa: E402

VOCABULARY_PATH: Path = SEER.parent / "vocabulary.tiktoken"
SCHEMA_PATH: Path = HERE / "schema.sql"
DATA_PATH: Path = HERE / "data.sql"
QUERIES_PATH: Path = HERE / "cases.yaml"

# The shell truncates a status to a byte and treats the top of the range as a
# signal, so a run with more failures than this still reports the same defeat.
MAX_STATUS: int = 125


@dataclass(frozen=True)
class Verdict:
    """What one record came to: the feed, and the validation results where it ran."""

    outcome: Outcome
    validations: tuple[Validation, ...] = ()

    def passed(self, record: Record) -> bool:
        if self.outcome.state != record.expect:
            return False

        return all(validation.succeeded for validation in self.validations)

    def explain(self, record: Record) -> str:
        if self.outcome.state != record.expect:
            return f"expected {record.expect}, {self.outcome.describe(record.query)}"

        failures: list[str] = [
            f"{validation.validator} refused it: {validation.error}"
            for validation in self.validations
            if not validation.succeeded
        ]
        return "; ".join(failures)


def judge(record: Record, feeder: Feeder, validators: tuple[Validator, ...]) -> Verdict:
    """Feed `record`, and run every validator where it is legal and completed."""

    outcome: Outcome = feeder.feed(record.query)

    # The declared outcome is checked first: a legal query must complete and an
    # illegal one must get stuck. Only legal completed queries are validated.
    if not record.is_legal or not outcome.completed:
        return Verdict(outcome)

    results = tuple(validator.validate(record.query) for validator in validators)
    return Verdict(outcome, results)


@dataclass
class Tally:
    failed: list[Record] = field(default_factory=list)
    passed_by_validator: dict[str, int] = field(default_factory=dict)
    empty_sqlite: int = 0


def run(
    records: list[Record],
    feeder: Feeder,
    validators: tuple[Validator, ...],
    verbose: bool = False,
) -> Tally:
    """Judge every record against the feeder and all validators."""

    tally = Tally(passed_by_validator={validator.name: 0 for validator in validators})
    heading: str = ""
    bar: Bar = Bar(len(records))

    for record in records:
        bar.draw(record.group)

        verdict: Verdict = judge(record, feeder, validators)
        passed: bool = verdict.passed(record)

        if not passed:
            tally.failed.append(record)

        for validation in verdict.validations:
            if validation.succeeded:
                tally.passed_by_validator[validation.validator] += 1
                if validation.rows == 0:
                    tally.empty_sqlite += 1

        bar.record(passed)

        if not verbose and passed:
            continue

        bar.clear()

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
        description="Feed every query of the corpus into the engine, and validate legal ones across all suites.",
    )

    parser.add_argument("--queries", type=Path, default=QUERIES_PATH)
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--vocabulary", type=Path, default=VOCABULARY_PATH)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--budget", type=float, default=2.0, help="seconds a query may run in SQLite")
    parser.add_argument("-v", "--verbose", action="store_true", help="print every record")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args: argparse.Namespace = parse_args(argv)

    validators: tuple[Validator, ...] = ()
    try:
        records: list[Record] = read_records(args.queries)
        schema_sql: str = args.schema.read_text(encoding="utf-8")
        data_sql: str = args.data.read_text(encoding="utf-8")
        schema: Schema | None = parse_schema(schema_sql)

        if schema is None:
            raise RuntimeError(f"Failed to parse {args.schema}")

        feeder = Feeder(args.vocabulary, schema, args.threads)
        validators = (
            SQLiteValidator(schema_sql, data_sql, args.budget),
            SqlglotValidator(schema_sql),
        )
    except (OSError, RuntimeError) as error:
        for validator in validators:
            validator.close()
        print(f"Failed to start: {error}", file=sys.stderr)
        return MAX_STATUS

    try:
        tally: Tally = run(records, feeder, validators, args.verbose)
    finally:
        for validator in validators:
            validator.close()

    legal: int = sum(1 for record in records if record.is_legal)

    print(
        f"\n{len(records) - len(tally.failed)}/{len(records)} records behaved as declared "
        f"({legal} legal, {len(records) - legal} illegal)"
    )

    for validator in validators:
        passed_count = tally.passed_by_validator[validator.name]
        extra = f" ({tally.empty_sqlite} returned no rows)" if validator.name == SQLiteValidator.name else ""
        print(f"{passed_count}/{legal} legal records passed {validator.name}{extra}")

    return min(len(tally.failed), MAX_STATUS)


if __name__ == "__main__":
    raise SystemExit(main())
