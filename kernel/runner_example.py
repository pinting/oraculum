"""The dynamic API: a factory, a head pool, and a group index.

    python runner_example.py

`example.py` owns its indexes and walks them by hand. This one owns nothing:
the factory keeps every index and answers with an id, the runner keeps the
heads walking them, and the graph is decided here, one notification at a time.

The language is `<greeting> <alias>?` where the alias is any identifier that is
not one of the reserved words -- which is a group: the identifier pattern minus
one lattice per word to keep out.
"""

from __future__ import annotations

import time

import kernel_typed as kl

VOCABULARY_PATH: str = "../vocabulary.tiktoken"
EOS_ID: int = 1

IDENTIFIER: str = "[a-zA-Z_][a-zA-Z0-9_]*"
RESERVED: list[str] = ["hello", "world", "monday", "friday", "select", "from"]

def build_alias(factory: kl.Factory) -> int:
    """The identifier pattern minus every reserved word."""

    include: int | None = factory.expression(IDENTIFIER)

    assert include is not None

    excludes: list[int] = []

    for word in RESERVED:
        index: int | None = factory.lattice(word)

        assert index is not None

        excludes.append(index)

    group: int | None = factory.group(include, excludes)

    assert group is not None

    return group

def main() -> int:
    start: float = time.perf_counter()
    vocabulary: kl.Vocabulary = kl.Vocabulary.from_file_path(VOCABULARY_PATH, EOS_ID)

    print(f"Vocabulary loaded in {1000 * (time.perf_counter() - start):.1f} ms")

    start = time.perf_counter()
    factory: kl.Factory = kl.Factory(vocabulary)

    print(f"Index bases built in {1000 * (time.perf_counter() - start):.1f} ms")

    alias: int = build_alias(factory)

    print(f"Alias group: {IDENTIFIER} minus {len(RESERVED)} words -> index {alias}")

    # The graph, as the payloads the runner will hand back. Each payload says
    # what comes after the head carrying it.
    after_alias: list[tuple[object, object]] = []
    after_space: list[tuple[object, object]] = [(alias, "alias")]
    after_greeting: list[tuple[object, object]] = [(("lattice", " "), "space")]

    graph: dict[str, list[tuple[object, object]] | None] = {
        "greeting": after_greeting,
        "space": after_space,
        # Nothing follows an alias, so the statement is complete once one is
        # matched: the runner is told by answering `None`.
        "alias": None,
    }

    runner: kl.Runner = kl.Runner(factory, workers=4)

    def resolve(head_id: int, payload: str, matched: str):
        """Called by the kernel when a head reaches the end of its index."""

        print(f"  head {head_id} finished {payload!r} with {matched!r}")

        return graph[payload]

    runner.set_resolver(resolve)
    runner.spawn(("lattice", "hello"), "greeting")
    runner.spawn(("lattice", "hi"), "greeting")

    print("\nType a token at a time. `hello` and `hi` open the statement,")
    print(f"then a space, then any identifier except {RESERVED}.\n")

    while not runner.is_completed():
        routes: list[int] = runner.routes().tolist()
        tokens: dict[str, int] = {}

        for token_id in routes:
            token: str | None = vocabulary.get_token_by_id(token_id)

            if token is not None:
                tokens[token] = token_id

        if not tokens:
            print("Nothing can follow; the statement is stuck.")

            break

        shown: list[str] = sorted(tokens)[:40]

        print(f"Heads: {[head.rule for head in runner.heads()]}")
        print("Routes: " + " ".join(f"`{token}`" for token in shown)
              + (" ..." if len(tokens) > len(shown) else ""))

        try:
            line: str = input("> ")
        except EOFError:
            return 0

        token_id = tokens.get(line)

        if token_id is None:
            print("Not a legal token here!")

            continue

        runner.feed(token_id)

        print(f"Matched: {runner.matched()!r}\n")

    rounds, notified, spawned = runner.stats

    print(f"\nDone: {runner.matched()!r}")
    print(f"{rounds} resolve rounds, {notified} notifications, {spawned} heads, "
          f"{factory.builds} index builds")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
