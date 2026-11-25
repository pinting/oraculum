"""Running completed legal queries against an in-memory SQLite database.

SQLite ships with Python and supports window functions (3.25+), RIGHT and
FULL joins (3.39+), recursive CTEs, and compound queries. Every query runs on a
time budget so non-terminating recursive queries fail cleanly instead of hanging
the test suite.
"""

from __future__ import annotations

import sqlite3
import time

from .base import Validation

# Minimum SQLite version required for RIGHT and FULL JOIN support.
MINIMUM_VERSION: tuple[int, int, int] = (3, 39, 0)

# Virtual machine instruction interval between deadline checks.
CHECK_EVERY: int = 1000


class SQLiteValidator:
    """Validates completed SQL queries by executing them in read-only SQLite."""

    name: str = "SQLite"
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
            self._connection.close()
            raise RuntimeError(f"Failed to build the SQLite database: {error}") from error

        self._connection.execute("PRAGMA query_only = ON")
        self._connection.set_progress_handler(self._expired, CHECK_EVERY)

    def _expired(self) -> bool:
        return time.monotonic() > self._deadline

    def validate(self, query: str) -> Validation:
        """Execute `query` within the time budget and return a `Validation`."""

        self._deadline = time.monotonic() + self._budget

        try:
            rows: list[tuple[object, ...]] = self._connection.execute(query).fetchall()
        except sqlite3.OperationalError as error:
            if self._expired():
                return Validation(self.name, error=f"did not finish within {self._budget:g}s")
            return Validation(self.name, error=str(error))
        except sqlite3.Error as error:
            return Validation(self.name, error=str(error))

        return Validation(self.name, rows=len(rows))

    def close(self) -> None:
        self._connection.close()
