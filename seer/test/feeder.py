"""Feeding one query into a fresh engine, one character at a time.

Every single character of the query has to be a token of its own, which the
Gemma vocabulary does supply for the whole of printable ASCII. A character it
does not spell is reported as a broken record rather than as a failure of the
engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import kernel as kl

from src import Context, Engine, IndexFactory, Schema, Thunk, root

from .corpus import COMPLETED, STUCK

EOS_ID: int = 1

@dataclass(frozen=True)
class Outcome:
    """What happened when a query was fed in.

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

    def describe(self, query: str) -> str:
        """Where a stuck feed stopped, as the text taken and the character refused."""

        taken: str = query[: self.consumed]
        rest: str = query[self.consumed :]

        return f"took {taken!r}, then {self.reason} at {rest[:1]!r}"

class Feeder:
    """A vocabulary, a schema and a grammar, reusable across queries.

    Loading the vocabulary and building the Aho-Corasick and TokTrie bases over
    it costs about half a second, and the factory memoises every index it
    builds, so both are made once and every query gets a fresh `Engine` over
    them. The engine holds all the per-query state; nothing leaks between runs.
    """

    def __init__(self, vocabulary_path: Path, schema: Schema, threads: int = 1) -> None:
        self.vocabulary: kl.Vocabulary = kl.Vocabulary.from_file_path(str(vocabulary_path), EOS_ID)
        self.schema: Schema = schema
        self.factory: IndexFactory = IndexFactory(self.vocabulary)
        self.threads: int = threads

        # The graph holds no state of its own - every branch carries its
        # context - so one is built and walked by every query.
        self.grammar: Thunk = root()

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
            Context(self.schema),
            self.grammar,
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
