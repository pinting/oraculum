"""Running one query in SQLite, built from the schema and filled with the data.

SQLite is the database the suite checks against because it ships with Python
and speaks everything the subset writes: window functions since 3.25, RIGHT
and FULL joins since 3.39, recursive definitions and compound queries since
long before. An older library is refused on start rather than blamed for
queries it cannot parse.

What running a query proves is that it is SQL: every name resolves, every
function exists with the arguments it was given, the syntax is the database's
own. It does not prove the query is meaningful - SQLite lets an ungrouped
column through where PostgreSQL would not - which is the half the engine's own
rules carry, and they are stricter than either.

The database is in memory, built once per run with its foreign keys enforced
while the data goes in, and read-only afterwards. Every query runs on a time
budget: a recursive definition that never stops is a statement that does not
work, and the budget reports it as one instead of hanging the suite.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

# What the subset needs of the library: RIGHT and FULL JOIN.
MINIMUM_VERSION: tuple[int, int, int] = (3, 39, 0)

# How many virtual machine instructions run between two looks at the clock.
CHECK_EVERY: int = 1000

@dataclass(frozen=True)
class Execution:
    """What running a query came to: how many rows, or why it failed."""

    rows: int = 0
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None

class Database:
    __slots__ = ("_connection", "_budget", "_deadline")

    def __init__(self, schema: str, data: str, budget: float = 2.0) -> None:
        if sqlite3.sqlite_version_info < MINIMUM_VERSION:
            required: str = ".".join(map(str, MINIMUM_VERSION))

            raise RuntimeError(f"SQLite {sqlite3.sqlite_version} is too old, {required} is needed")

        self._connection: sqlite3.Connection = sqlite3.connect(":memory:")
        self._budget: float = budget
        self._deadline: float = 0.0

        try:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.executescript(schema)
            self._connection.executescript(data)
        except sqlite3.Error as error:
            raise RuntimeError(f"Failed to build the database: {error}") from error

        self._connection.execute("PRAGMA query_only = ON")

        # SQLite calls this every few instructions; a true answer aborts the
        # statement, which is how a query past its budget is stopped.
        self._connection.set_progress_handler(self._expired, CHECK_EVERY)

    def _expired(self) -> bool:
        return time.monotonic() > self._deadline

    def run(self, query: str) -> Execution:
        """Run `query` to the end, within the budget."""

        self._deadline = time.monotonic() + self._budget

        try:
            rows: list[tuple] = self._connection.execute(query).fetchall()
        except sqlite3.OperationalError as error:
            if self._expired():
                return Execution(error=f"did not finish within {self._budget:g}s")

            return Execution(error=str(error))
        except sqlite3.Error as error:
            return Execution(error=str(error))

        return Execution(rows=len(rows))

    def close(self) -> None:
        self._connection.close()
