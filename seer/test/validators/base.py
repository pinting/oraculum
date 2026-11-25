"""Shared types for integration test query validators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Validation:
    """Outcome of checking a single completed SQL query against one validator."""

    validator: str
    error: str | None = None
    rows: int | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


class Validator(Protocol):
    """Interface implemented by every post-completion SQL validator."""

    name: str

    def validate(self, query: str) -> Validation:
        """Validate `query` and return its `Validation` result."""
        ...

    def close(self) -> None:
        """Release any resources held by the validator."""
        ...
