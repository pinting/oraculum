"""The corpus: `cases.yaml`, read into records.

The file is a list of groups. A group names one idea, carries the `expect`
that idea asserts and the queries it asserts it over, so the expectation is
written once per idea rather than once per query and a failure can say which
idea broke.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# The two outcomes a feed has, and the two words `expect` may be written with.
COMPLETED: str = "completed"
STUCK: str = "stuck"

EXPECTATIONS: frozenset[str] = frozenset({COMPLETED, STUCK})

@dataclass(frozen=True)
class Record:
    """One query, with the group it was declared in for the report."""

    group: str
    query: str
    expect: str
    """`COMPLETED` or `STUCK` - what feeding the query has to end in."""

    @property
    def is_legal(self) -> bool:
        return self.expect == COMPLETED

def read_records(path: Path) -> list[Record]:
    """The corpus, flattened, every query tagged with its group."""

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
