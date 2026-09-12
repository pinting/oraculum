"""Expression build, scan and lookup timings, from Python.

For each pattern below: how long the `Expression` takes to build, how long a
node takes to answer with its whole route set, how long one transition lookup
costs, and how much memory the index then holds.

This does not run as it stands. It asks for a DFA layout per round and for
TokTrie tuning parameters, and the bindings expose neither - the layout is a
type parameter, fixed to `FlatDFA` when the extension is compiled. Comparing
layouts is therefore only possible from Rust, which is what
`src/bin/benchmark.rs` is for.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from numpy.typing import NDArray

import kernel_typed as kl

VOCABULARY_PATH: str = "../vocabulary.tiktoken"
EOS_ID: int = 1

NUM_ROUNDS: int = 100
NUM_SCAN_ITERS: int = 50
NUM_LOOKUP_ITERS: int = 200

NAME_WIDTH: int = 20
VALUE_WIDTH: int = 12

PATTERNS: list[str] = [
    "hi",
    "ok",
    "no",
    "yes",
    "cat",
    "dog",
    "red",
    "sun",
    "moon",
    "tree",
    "hello",
    "world",
    "apple",
    "house",
    "river",
    "a|b|c",
    "x|y|z",
    "go|no",
    "up|down",
    "left|right",
    "[a-z]",
    "[0-9]",
    "[A-Z]+",
    "[a-z]{2}",
    "[0-9]{3}",
    "foo|bar|baz",
    "one|two|three",
    "red|green|blue",
    "cat|dog|bird|fish",
    "mon|tue|wed|thu|fri",
    "ab+c",
    "a*b+",
    "x+y+z+",
    "go+d",
    "ba+na+na",
    "colou?r",
    "behaviou?r",
    "favou?rite",
    "grey|gray",
    "analyse|analyze",
    "[aeiou]{2}",
    "[bcdfg]{3}",
    "[a-f0-9]{4}",
    "[a-z][0-9]",
    "[A-Z][a-z]+",
    "the|a|an",
    "is|am|are|was|were",
    "I|you|he|she|it|we|they",
    "in|on|at|by|to|for",
    "and|but|or|nor|yet|so",
    "(ab)+",
    "(xy)+z",
    "a(bc)*d",
    "(ha){2,4}",
    "(la){3}",
    "[a-z]{1,5}",
    "[0-9]{2,4}",
    "[a-z]{3,6}",
    "[A-Za-z]{2,8}",
    "[a-z0-9]{4,8}",
    "https?://[a-z]+",
    "www\\.[a-z]+",
    "[a-z]+@[a-z]+",
    "[0-9]+\\.[0-9]+",
    "[a-z]+\\.[a-z]{2,4}",
    "(foo|bar)(baz|qux)",
    "(ab|cd)(ef|gh)(ij|kl)",
    "(red|blue)(car|bus)",
    "(big|small)(cat|dog|rat)",
    "(hot|cold)(day|night)",
    "a{1,3}b{1,3}c{1,3}",
    "x{2,5}y{2,5}",
    "[abc]{2}[def]{2}[ghi]{2}",
    "[a-c]{3}[d-f]{3}",
    "[0-3]{2}[4-7]{2}[8-9]{2}",
    "monday|tuesday|wednesday|thursday|friday|saturday|sunday",
    "january|february|march|april|may|june|july|august|september|october|november|december",
    "alpha|beta|gamma|delta|epsilon|zeta|eta|theta",
    "mercury|venus|earth|mars|jupiter|saturn|uranus|neptune",
    "spring|summer|autumn|winter|monsoon|drought",
    "(north|south)(east|west)?",
    "(pre|post|un|re)[a-z]{3,6}",
    "(auto|semi|anti)[a-z]{4,8}",
    "(over|under)(flow|line|pass|take)",
    "(black|white|grey)(bird|fish|wolf|bear)",
    "[a-z]{2,4}(ing|tion|ment|ness|able)",
    "[a-z]{3,5}(ed|er|est|ly|ful)",
    "[bcdfghjklmnpqrstvwxyz][aeiou][bcdfghjklmnpqrstvwxyz]{1,3}",
    "[aeiou][bcdfghjklmnpqrstvwxyz]{2}[aeiou]",
    "[a-z]{2}[0-9]{2}[a-z]{2}[0-9]{2}",
    "(do|re|mi|fa|sol|la|si){2,4}",
    "(ab|cd|ef|gh|ij|kl|mn|op){2,3}",
    "(foo|bar|baz|qux|quux|corge|grault|garply){1,3}",
    "(alpha|beta|gamma)(one|two|three)(red|blue|green)",
    "(north|south|east|west)(ern)?(most)?",
    "(un|re|dis|mis|pre|post)(connect|appear|cover|place|view|build)",
    "(over|under|out|up)(run|grow|come|turn|look|stand|play|line)",
    "[A-Z][a-z]{2,6}(son|ton|berg|stein|ville|burg|ford|wood|land|field)",
    "[a-z]{3,8}(ation|ition|ution|ision|usion|ption|ntion|stion|ction)",
    "(inter|intra|extra|ultra|super|hyper)(nation|state|galactic|sonic|natural|active)",
]

@dataclass
class DFAResult:
    name: str
    build_times_ms: list[float] = field(default_factory=list)
    scan_times_us: list[float] = field(default_factory=list)
    lookup_times_us: list[float] = field(default_factory=list)
    memory_usages: list[int] = field(default_factory=list)
    failures: int = 0

DFA_CONFIGS: list[tuple[str, int]] = [
    ("FastHashDFA", kl.FAST_HASH_DFA),
    ("DoubleHashDFA", kl.DOUBLE_HASH_DFA),
    ("FlatDFA", kl.FLAT_DFA),
]

def benchmark_expression(
    pattern: str,
    vocabulary: kl.Vocabulary,
    toktrie: kl.TokTrie,
    result: DFAResult,
) -> None:
    """Time one pattern on one layout, appending to `result`.

    A pattern that fails to build is counted rather than raised on, so one bad
    case does not lose the whole run.
    """

    try:
        start: float = time.perf_counter()
        expression: kl.Expression = kl.Expression(pattern, vocabulary, toktrie)
        built: float = time.perf_counter()

        result.build_times_ms.append((built - start) * 1000)
        result.memory_usages.append(expression.memory_usage())
    except Exception:
        result.failures += 1

        return

    start_node: int = 0
    transitions: NDArray[np.uint64] = np.array([], dtype=np.uint64)

    start = time.perf_counter()

    for _ in range(NUM_SCAN_ITERS):
        transitions = expression.transitions(start_node)

    elapsed: float = time.perf_counter() - start

    result.scan_times_us.append(elapsed / NUM_SCAN_ITERS * 1_000_000)

    if not transitions.size:
        result.lookup_times_us.append(0.0)

        return

    token_ids: list[int] = transitions.tolist()

    random.seed(42)

    sample_ids: list[int] = [
        token_ids[random.randint(0, len(token_ids) - 1)]
        for _ in range(min(10, len(token_ids)))
    ]

    start = time.perf_counter()

    for _ in range(NUM_LOOKUP_ITERS):
        for token_id in sample_ids:
            expression.next(start_node, int(token_id))

    elapsed = time.perf_counter() - start
    lookups: int = NUM_LOOKUP_ITERS * len(sample_ids)

    result.lookup_times_us.append(elapsed / lookups * 1_000_000)

def avg(values: list[float]) -> float:
    if not values:
        return 0.0

    return sum(values) / len(values)

def print_single_leaderboard(
    title: str,
    results: list[DFAResult],
    value_fn: Callable[[DFAResult], float],
    unit: str,
) -> None:
    ranked: list[DFAResult] = sorted(results, key=value_fn)

    header: str = f"{'DFA Type':<{NAME_WIDTH}}{f'Avg ({unit})':>{VALUE_WIDTH}}"
    rule: str = "-" * len(header)

    print(f"{title}:")
    print(rule)
    print(header)
    print(rule)

    for position, result in enumerate(ranked):
        name: str = f"#{position + 1} {result.name}"

        print(f"{name:<{NAME_WIDTH}}{value_fn(result):>{VALUE_WIDTH}.3f}")

    print(rule)
    print()

def print_leaderboard(results: list[DFAResult]) -> None:
    print()

    print_single_leaderboard(
        "LOOKUP LEADERBOARD",
        results,
        lambda result: avg(result.lookup_times_us),
        "us",
    )

    print_single_leaderboard(
        "SCAN LEADERBOARD",
        results,
        lambda result: avg(result.scan_times_us),
        "us",
    )

    print_single_leaderboard(
        "BUILD LEADERBOARD",
        results,
        lambda result: avg(result.build_times_ms),
        "ms",
    )

    print_single_leaderboard(
        "MEMORY LEADERBOARD",
        results,
        lambda result: avg([float(usage) for usage in result.memory_usages]) / 1024,
        "KB",
    )

def main() -> None:
    print("Loading vocabulary...")

    try:
        vocabulary: kl.Vocabulary = kl.Vocabulary.from_file_path(VOCABULARY_PATH, EOS_ID, 32)
    except Exception:
        print(f"Error: {VOCABULARY_PATH} not found.")

        return

    eos_id: int = vocabulary.get_eos_id()
    total_cases: int = NUM_ROUNDS * len(PATTERNS)

    print(f"Vocabulary loaded (eos_id={eos_id})")
    print(f"Building TokTrie bases for all {len(DFA_CONFIGS)} DFA types...")

    toktries: dict[int, kl.TokTrie] = {}

    for name, dfa_type in DFA_CONFIGS:
        start: float = time.perf_counter()
        toktries[dfa_type] = kl.TokTrie(vocabulary, dfa_type, 32, 32)
        elapsed: float = time.perf_counter() - start

        print(f"  {name} TokTrie built in {elapsed * 1000:.1f} ms")

    print(
        f"\nRunning benchmark: {len(PATTERNS)} patterns"
        f" x {len(DFA_CONFIGS)} DFA types x {NUM_ROUNDS} rounds"
    )
    print(f"Cases per DFA type: {total_cases}")
    print(f"Scan iterations per case: {NUM_SCAN_ITERS}")
    print(f"Lookup iterations per case: {NUM_LOOKUP_ITERS}")
    print()

    results: list[DFAResult] = [DFAResult(name=name) for name, _ in DFA_CONFIGS]

    for round_index in range(NUM_ROUNDS):
        for pattern_index, pattern in enumerate(PATTERNS):
            case: int = round_index * len(PATTERNS) + pattern_index + 1

            print(
                f"\r[{case:5d}/{total_cases}]"
                f" Round {round_index + 1}/{NUM_ROUNDS}"
                f" - Pattern: {pattern[:50]:<50s}",
                end="",
                flush=True,
            )

            for position, (_, dfa_type) in enumerate(DFA_CONFIGS):
                benchmark_expression(
                    pattern,
                    vocabulary,
                    toktries[dfa_type],
                    results[position],
                )

    print("\n\nBenchmark complete!")

    print_leaderboard(results)

if __name__ == "__main__":
    main()
