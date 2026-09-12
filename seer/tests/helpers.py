"""Helpers for driving the engine in tests."""

from __future__ import annotations

import kernel as kl

from src.engine import Engine
from src.schema import Schema
from src.factory import IndexFactory
from src.graph import root

def drive(
    vocabulary: kl.Vocabulary,
    schema: Schema,
    target: str,
    factory: IndexFactory | None = None,
    threads: int = 1,
) -> tuple[bool, str]:
    """Feed `target` into a fresh engine, always taking the longest legal token.

    Returns whether the statement completed and how much of it was matched.
    """

    engine: Engine = Engine(vocabulary, schema, root(), factory=factory, threads=threads)
    position: int = 0

    while position < len(target):
        allowed: dict[str, int] = {}

        for token_id in engine.routes().tolist():
            token: str | None = engine.get_token(token_id)

            if token is not None and target.startswith(token, position):
                allowed[token] = token_id

        if not allowed:
            return False, engine.matched()

        longest: str = max(allowed, key=len)

        if not engine.feed(allowed[longest]):
            return False, engine.matched()

        position += len(longest)

    return engine.is_completed(), engine.matched()

def trace(
    vocabulary: kl.Vocabulary,
    schema: Schema,
    target: str,
    factory: IndexFactory | None = None,
    threads: int = 1,
) -> list[tuple[tuple[int, ...], tuple[str, ...]]]:
    """Record the allowed routes and live heads at every step."""

    engine: Engine = Engine(vocabulary, schema, root(), factory=factory, threads=threads)

    steps: list[tuple[tuple[int, ...], tuple[str, ...]]] = []
    position: int = 0

    while position < len(target):
        routes: list[int] = sorted(engine.routes().tolist())

        steps.append((tuple(routes), tuple(sorted(head.rule for head in engine.heads))))

        allowed: dict[str, int] = {}

        for token_id in routes:
            token: str | None = engine.get_token(token_id)

            if token is not None and target.startswith(token, position):
                allowed[token] = token_id

        if not allowed:
            break

        longest: str = max(allowed, key=len)

        if not engine.feed(allowed[longest]):
            break

        position += len(longest)

    return steps
