"""The patterns the grammar spells its separators and identifiers with."""

from __future__ import annotations

IDENTIFIER: str = r"[a-zA-Z_][a-zA-Z0-9_]*"
WHITESPACE: str = r"[ \n\t]+"
COMMA: str = r"[ \n\t]*,[ \n\t]*"

# The brackets carry their own inner whitespace, so `(a = b)` and `( a = b )`
# are both reachable without an index that accepts the empty word.
LPAREN: str = r"\([ \n\t]*"
RPAREN: str = r"[ \n\t]*\)"

# The terminator carries the whitespace in front of it for the same reason.
# Whitespace between tokens is free, and the `;` is a token like any other, so
# `users;` and `users ;` are both the end of the statement. As a lattice it
# would be neither - a head that had taken a space would have nothing but
# `WHERE` and the join types left, and a statement that had stepped away from
# its last table could never come back to close.
TERMINATOR: str = r"[ \n\t]*;"

# How deep the parentheses of a condition clause may nest. The graph is
# generative, so without a cap nothing would ever stop offering another `(`.
NESTING_LIMIT: int = 3

def insensitive(word: str) -> str:
    """A pattern spelling `word` in any case, which is how SQL compares identifiers."""

    def spell(character: str) -> str:
        if character.isalpha() and character.lower() != character.upper():
            return f"[{character.lower()}{character.upper()}]"

        if character.isalnum() or character == "_":
            return character

        return "\\" + character

    return "".join(spell(character) for character in word)
