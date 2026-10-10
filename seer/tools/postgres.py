"""Statements run in PostgreSQL: `make postgres`.

SQLite is what the test suite runs every legal query in, and it is lenient:
it lets an ungrouped column through and compares anything with anything. The
README promises statements that run in PostgreSQL as well, so this runs them
there - the legal records of a corpus, or the statements `tools.fuzz` wrote -
in a throwaway PostgreSQL 16 built over the schema and filled from the data.

The server comes from `pgserver`, which ships its binaries as a wheel but has
none for Python 3.14, so this runs under the interpreter `make postgres`
builds for it, and reads nothing of seer but the corpus.

A statement PostgreSQL refuses is one of three things:

    out of scope    the value of a literal, which seer never checks - a
                    `'2024-99-99'` has the shape of a timestamp - or a
                    statement that ran out of time, which is still SQL
    known           a limit of the type classes, which seer does not track
                    finely enough for PostgreSQL: a recursive definition whose
                    member types differ in width alone (`integer` against
                    `bigint`), and a `json` column, which has neither equality
                    nor order
    refused         anything else, which is a statement seer should never
                    have written

Only the last fails the run; the exit status counts them.

    .postgres/bin/python tools/postgres.py test/cases.yaml
    .postgres/bin/python tools/postgres.py --schema tools/schemas/harsh.sql --data - out/fuzz/harsh.jsonl
"""

# pyright: reportMissingImports=false

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import warnings
from collections import Counter
from pathlib import Path

HERE: Path = Path(__file__).resolve().parent
SEER: Path = HERE.parent

if str(SEER) not in sys.path:
    sys.path.insert(0, str(SEER))

# platformdirs warns about a runtime directory a container does not have.
warnings.filterwarnings("ignore", module="platformdirs")

import pgserver  # noqa: E402
import psycopg  # noqa: E402

from test.corpus import read_records  # noqa: E402

SCHEMA_PATH: Path = SEER / "test" / "schema.sql"
DATA_PATH: Path = SEER / "test" / "data.sql"

MAX_STATUS: int = 125

OUT_OF_SCOPE: tuple[str, ...] = (
    "date/time field value out of range",
    "canceling statement due to statement timeout",
)

KNOWN: tuple[str, ...] = (
    "in non-recursive term but type",
    "could not identify an equality operator for type json",
    "could not identify an ordering operator for type json",
)

def read_queries(path: Path) -> list[str]:
    """The legal records of a corpus, or one JSON string per line of anything else."""

    if path.suffix in (".yaml", ".yml"):
        return [record.query for record in read_records(path) if record.is_legal]

    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]

def classify(error: str) -> str:
    if any(needle in error for needle in OUT_OF_SCOPE):
        return "out of scope"

    if any(needle in error for needle in KNOWN):
        return "known"

    return "refused"

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run statements seer wrote in PostgreSQL 16.")

    parser.add_argument("queries", type=Path, nargs="+", help="a corpus .yaml, or a .jsonl of statements")
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    parser.add_argument("--data", default=str(DATA_PATH), help="rows to fill the schema with; - for none")
    parser.add_argument("--budget", type=float, default=2.0, help="seconds a statement may run")

    args: argparse.Namespace = parser.parse_args(argv)

    try:
        queries: list[str] = [query for path in args.queries for query in read_queries(path)]
        schema: str = args.schema.read_text(encoding="utf-8")
        data: str = "" if args.data == "-" else Path(args.data).read_text(encoding="utf-8")
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Failed to start: {error}", file=sys.stderr)

        return MAX_STATUS

    tally: Counter[str] = Counter()
    errors: Counter[tuple[str, str]] = Counter()

    with pgserver.get_server(tempfile.mkdtemp(prefix="seer-postgres-"), cleanup_mode="delete") as server:
        with psycopg.connect(server.get_uri(), autocommit=True) as connection:
            connection.execute(schema)

            if data:
                connection.execute(data)

            connection.execute(f"SET statement_timeout = {int(args.budget * 1000)}")

            for query in queries:
                try:
                    connection.execute(query).fetchall()
                except psycopg.Error as error:
                    message: str = str(error).splitlines()[0]
                    kind: str = classify(message)

                    tally[kind] += 1
                    errors[(kind, message)] += 1

                    if kind == "refused":
                        print(f"  REFUSED  {query!r}\n           {message}")
                else:
                    tally["ran"] += 1

    print(
        f"\n{len(queries)} statements over {args.schema.name}: {tally['ran']} ran in PostgreSQL, "
        f"{tally['out of scope']} out of scope, {tally['known']} known, {tally['refused']} refused"
    )

    for (kind, message), count in sorted(errors.items(), key=lambda item: -item[1]):
        if kind != "refused":
            print(f"  {count:5d}  {kind:12s}  {message}")

    return min(tally["refused"], MAX_STATUS)

if __name__ == "__main__":
    raise SystemExit(main())
