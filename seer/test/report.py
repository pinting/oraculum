"""The progress bar the run draws while it feeds the corpus."""

from __future__ import annotations

import shutil
import sys
from typing import TextIO

# How many cells the bar itself is drawn with, whatever the terminal width.
BAR_WIDTH: int = 24

class Bar:
    """A one line progress indicator, drawn only onto a terminal.

    It owns the last line of the output. `clear` takes that line back so a
    failing record can be printed above it and `draw` puts it down again, which
    is what keeps the report and the bar from overwriting each other.

    A redirected stdout gets none of it - a pipe, a log or `make test` under CI
    keeps just the report - and neither does a stream that cannot encode the
    block characters, which fall back to ASCII rather than raising.
    """

    __slots__ = ("_stream", "_total", "_live", "_full", "_empty", "_done", "_failed", "_drawn")

    def __init__(self, total: int, stream: TextIO | None = None) -> None:
        self._stream: TextIO = stream if stream is not None else sys.stdout
        self._total = total
        self._live = total > 0 and self._stream.isatty()

        self._full, self._empty = self._characters()

        self._done: int = 0
        self._failed: int = 0

        # The width of the line currently on screen, which is what `clear` has
        # to blank. Zero means the terminal's last line is not ours.
        self._drawn: int = 0

    def _characters(self) -> tuple[str, str]:
        """Blocks where the stream can encode them, dashes where it cannot."""

        encoding: str = self._stream.encoding or "ascii"

        try:
            "\u2588\u2591".encode(encoding)
        except (UnicodeError, LookupError):
            return "#", "-"

        return "\u2588", "\u2591"

    def clear(self) -> None:
        """Blank the bar's line and give it back to whoever prints next."""

        if not self._drawn:
            return

        self._stream.write("\r" + " " * self._drawn + "\r")
        self._stream.flush()

        self._drawn = 0

    def draw(self, group: str) -> None:
        """Redraw the bar, naming the group whose record is about to be fed."""

        if not self._live:
            return

        filled: int = self._done * BAR_WIDTH // self._total
        counter: str = f"{self._done:>{len(str(self._total))}}/{self._total}"
        tally: str = f", {self._failed} failed" if self._failed else ""

        line: str = (
            f"[{self._full * filled}{self._empty * (BAR_WIDTH - filled)}] "
            f"{counter}{tally}  {group}"
        )

        # One column is left free so a terminal that wraps on the last cell
        # does not scroll the report away.
        limit: int = shutil.get_terminal_size((80, 24)).columns - 1

        if len(line) > limit:
            line = line[: max(limit, 0)]

        self.clear()

        self._stream.write(line)
        self._stream.flush()

        self._drawn = len(line)

    def record(self, passed: bool) -> None:
        self._done += 1

        if not passed:
            self._failed += 1
