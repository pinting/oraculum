"""Benchmarks for the kernel's worker pool.

    python benchmark.py

Reports four things:

1. how well raw `kernel` index construction scales across threads, which is
   the ceiling for everything else;
2. how the engine's cold-start expansion scales as the schema widens, which is
   where the head pool has real fan-out;
3. warm per-token latency, where the index registry is hot and there is little
   left to parallelise;
4. what a group index costs per head, since alias resolution puts one exclusion
   per reserved word, table and field behind every alias.
"""

from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import kernel as kl

from core import EOS_ID, SCHEMA, VOCABULARY_PATH
from src import (
    Context,
    Engine,
    IndexDraft,
    IndexFactory,
    Schema,
    parse_schema,
    root,
)
from src.graph import IDENTIFIER

WIDTHS: list[tuple[int, int]] = [(5, 5), (15, 15), (30, 25), (60, 40)]
THREAD_COUNTS: list[int] = [1, 2, 4, 8]

def wide_schema(table_count: int, field_count: int) -> str:
    """A schema with `table_count` tables of `field_count` distinct fields each.

    Each table also carries a foreign key to the one before it, so the join
    graph is a chain rather than a set of isolated nodes.
    """

    statements: list[str] = []

    for table in range(table_count):
        columns: list[str] = [
            f"    t{table}_col{column} TEXT," for column in range(field_count)
        ]

        if table:
            columns.append(f"    t{table}_parent BIGINT REFERENCES table{table - 1}(id),")

        body: str = "\n".join(columns)

        statements.append(
            f"CREATE TABLE table{table} (\n    id BIGINT PRIMARY KEY,\n{body}\n);"
        )

    return "\n".join(statements)

def best_of(runs: int, work) -> float:
    """Fastest wall clock time over `runs` repetitions, in seconds."""

    return min(_timed(work) for _ in range(runs))

def _timed(work) -> float:
    start: float = time.perf_counter()

    work()

    return time.perf_counter() - start

def best_of_fed(runs: int, build, tokens: list[int]) -> float:
    """Fastest time to feed `tokens`, with a fresh engine per run.

    `build` is called outside the measurement. It has to be, because building
    an `Engine` constructs the `Context` -- and with it the GF(2) ring of
    `root.py`, which for a wide schema costs more than everything being
    measured put together and has nothing to do with the head pool.
    """

    best: float = float("inf")

    for _ in range(runs):
        engine = build()

        start: float = time.perf_counter()

        for token_id in tokens:
            engine.feed(token_id)

        best = min(best, time.perf_counter() - start)

    return best

def rule(title: str) -> None:
    print(f"\n{title}")
    print("-" * 64)

def bench_index_building(vocabulary: kl.Vocabulary, runs: int) -> None:
    """Raw `kernel` throughput -- the ceiling the worker pool works against."""

    rule("INDEX CONSTRUCTION (16 distinct expressions)")

    trie_base: kl.TokTrie = kl.TokTrie.new(vocabulary)
    patterns: list[str] = [
        rf"[a-zA-Z_][a-zA-Z0-9_]*_{i}" for i in range(16)
    ]

    def build_all() -> None:
        for pattern in patterns:
            kl.Expression(pattern, vocabulary, trie_base)

    baseline: float = best_of(runs, build_all)

    print(f"{'threads':>10}{'time (ms)':>14}{'speedup':>12}")

    for threads in THREAD_COUNTS:
        if threads == 1:
            elapsed: float = baseline
        else:
            with ThreadPoolExecutor(threads) as pool:
                def build_parallel() -> None:
                    list(pool.map(lambda p: kl.Expression(p, vocabulary, trie_base), patterns))

                elapsed = best_of(runs, build_parallel)

        print(f"{threads:>10}{1000 * elapsed:>14.1f}{baseline / elapsed:>11.2f}x")

def bench_cold_expansion(vocabulary: kl.Vocabulary, factory: IndexFactory, runs: int) -> None:
    """Cold `SELECT ` expansion, where every field becomes a head."""

    rule("COLD HEAD RESOLUTION (SELECT + space, empty index registry)")

    print("Engine construction is excluded: it is schema setup, not resolution.\n")

    select_id: int | None = vocabulary.get_id_by_token("SELECT")
    space_id: int | None = vocabulary.get_id_by_token(" ")

    if select_id is None or space_id is None:
        print("vocabulary is missing the SELECT / space tokens")

        return

    header: str = f"{'schema':>14}{'fields':>9}"

    for threads in THREAD_COUNTS:
        header += f"{('1 thr' if threads == 1 else f'{threads} thr'):>11}"

    print(header + f"{'best':>10}")

    for table_count, field_count in WIDTHS:
        tables: Schema | None = parse_schema(wide_schema(table_count, field_count))

        if tables is None:
            continue

        fields: int = len(tables.get_all_fields())

        row: str = f"{f'{table_count}x{field_count}':>14}{fields:>9}"
        timings: list[float] = []

        for threads in THREAD_COUNTS:
            def build(threads: int = threads) -> Engine:
                return Engine(
                    vocabulary, tables, root(), factory=factory.fork(), threads=threads
                )

            elapsed: float = best_of_fed(runs, build, [select_id, space_id])

            timings.append(elapsed)

            row += f"{1000 * elapsed:>11.1f}"

        speedup: float = timings[0] / min(timings)

        print(row + f"{speedup:>9.2f}x")

    print("\n(ms, lower is better; `best` is the serial time over the fastest thread count)")

def bench_warm_steps(vocabulary: kl.Vocabulary, factory: IndexFactory, runs: int) -> None:
    """Per-token latency once the index cache is warm."""

    rule("WARM PER-TOKEN LATENCY")

    tables: Schema | None = parse_schema(SCHEMA)

    if tables is None:
        return

    statement: list[str] = ["SELECT", " ", "email", " ", "FROM", " ", "users", ";"]

    warm: IndexFactory = factory.fork()

    # Warm the registry before measuring, so neither configuration is charged
    # for the one-off index builds of the first pass.
    warmup: Engine = Engine(vocabulary, tables, root(), factory=warm)

    for token in statement:
        token_id = warmup.get_token_id(token)

        if token_id is not None:
            warmup.feed(token_id)

    for threads in (1, 4):
        samples: list[float] = []

        for _ in range(runs):
            engine: Engine = Engine(
                vocabulary, tables, root(), factory=warm, threads=threads
            )

            for token in statement:
                token_id: int | None = engine.get_token_id(token)

                if token_id is None:
                    continue

                start: float = time.perf_counter()

                engine.feed(token_id)

                samples.append(time.perf_counter() - start)

        median: float = statistics.median(samples)
        worst: float = max(samples)

        print(f"{threads:>3} thread(s): median {1000 * median:6.3f} ms, max {1000 * worst:6.3f} ms")

def bench_groups(vocabulary: kl.Vocabulary, factory: IndexFactory, runs: int) -> None:
    """What subtracting the schema from the identifier pattern costs.

    A group holds one memory per member, so a head on the alias group walks the
    identifier DFA plus one tiny lattice per excluded name. This is the price of
    an alias being unambiguous.
    """

    rule("GROUP INDEX (identifier minus the reserved names)")

    tables: Schema | None = parse_schema(SCHEMA)

    if tables is None:
        return

    names: tuple[str, ...] = Context(tables).get_reserved_names()
    include: IndexDraft = IndexDraft.expression(IDENTIFIER)
    group: IndexDraft = IndexDraft.group(
        include, [IndexDraft.lattice(name) for name in names]
    )

    warm: IndexFactory = factory.fork()

    print(f"{len(names)} exclusions ({len(tables.get_names())} from the schema)")

    for label, draft in (("expression", include), ("group", group)):
        spec = warm.spec(draft)

        if spec is None:
            continue

        # Build once, then measure feeding: the head is what a group makes
        # more expensive, not the index.
        warm.create_index(draft)

        token_id: int | None = vocabulary.get_id_by_token("u")

        if token_id is None:
            continue

        def feed(spec=spec, token_id=token_id) -> None:
            walker: kl.Runner = kl.Runner(warm.unit, 1)

            walker.set_resolver(lambda _id, _payload, _matched: [])
            walker.spawn(spec, None)
            walker.feed(token_id)

        elapsed: float = best_of(runs * 20, feed)

        print(f"{label:>12}: spawn + one token in {1000 * elapsed:6.3f} ms")

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark the seer head pool.")

    parser.add_argument("--vocabulary", default=VOCABULARY_PATH)
    parser.add_argument("--eos-id", type=int, default=EOS_ID)
    parser.add_argument("--runs", type=int, default=3, help="repetitions per measurement")

    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    args: argparse.Namespace = parse_args(argv)

    start: float = time.perf_counter()
    vocabulary: kl.Vocabulary = kl.Vocabulary.from_file_path(args.vocabulary, args.eos_id)

    print(f"Vocabulary loaded in {1000 * (time.perf_counter() - start):.1f} ms "
          f"({len(vocabulary.get_tokens())} tokens)")

    start = time.perf_counter()
    factory: IndexFactory = IndexFactory(vocabulary)

    print(f"Index bases built in {1000 * (time.perf_counter() - start):.1f} ms")

    bench_index_building(vocabulary, args.runs)
    bench_cold_expansion(vocabulary, factory, args.runs)
    bench_warm_steps(vocabulary, factory, args.runs)
    bench_groups(vocabulary, factory, args.runs)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
