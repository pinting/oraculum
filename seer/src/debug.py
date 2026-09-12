"""Debug tracing for `Context`.

What makes a resolver readable is seeing the whole state after every step, so
every operation that modifies a `Context` prints one block: a heading naming
what was applied, then the state it produced.

Tracing is off by default, so importing the library stays silent; the driver
turns it on. It is cheap to leave on: selectors only run when a cursor reaches
an accepting state, so a whole statement produces a handful of blocks rather
than one per speculative expansion.
"""

from __future__ import annotations

import sys
import threading
from typing import Any, Callable, TextIO

WIDTH: int = 64

_enabled: bool = False
_stream: TextIO | None = None
_lock = threading.Lock()

def enable(stream: TextIO | None = None) -> None:
    """Start printing a state block after every modifying `Context` operation."""

    global _enabled, _stream

    _enabled = True
    _stream = stream if stream is not None else sys.stdout

def disable() -> None:
    global _enabled, _stream

    _enabled = False
    _stream = None

def is_enabled() -> bool:
    return _enabled

def trace(operation: str, state: Any) -> None:
    """Print `state` under a heading naming the operation that produced it.

    `state` is rendered lazily, so nothing is formatted while tracing is off -
    which matters because `Root.__str__` runs a sympy simplification.
    """

    if not _enabled:
        return

    render(operation, str(state))

def render(operation: str, body: str) -> None:
    stream: TextIO = _stream if _stream is not None else sys.stdout
    heading: str = f"── {operation} "
    rule: str = heading + "─" * max(WIDTH - len(heading), 0)

    # One write per block, so concurrent expander threads cannot interleave.
    with _lock:
        stream.write(f"\n{rule}\n{body}\n")
        stream.flush()

def traced(operation: Callable[..., str]):
    """Decorator marking a `Context` method as modifying.

    `operation` receives the same arguments as the method and returns the label
    for the heading, so a trace says what was applied and not merely which
    method ran. It is evaluated *before* the call, because a method may consume
    the state the label describes - `use_field` clears the open namespace.
    """

    def decorate(method):
        def wrapper(self, *args, **kwargs):
            label: str | None = operation(self, *args, **kwargs) if _enabled else None

            result = method(self, *args, **kwargs)

            if label is not None:
                trace(label, self)

            return result

        wrapper.__name__ = method.__name__
        wrapper.__doc__ = method.__doc__
        wrapper.__wrapped__ = method

        return wrapper

    return decorate
