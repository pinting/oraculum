from __future__ import annotations

import time
import random
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

import fastlines_typed as fl

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
    ("FastHashDFA", fl.FAST_HASH_DFA),
    ("DoubleHashDFA", fl.DOUBLE_HASH_DFA),
    ("FlatDFA", fl.FLAT_DFA),
]

NUM_ROUNDS = 10
NUM_SCAN_ITERS = 50
NUM_LOOKUP_ITERS = 200


def benchmark_expression(
    pattern: str,
    vocabulary: fl.Vocabulary,
    toktrie: fl.TokTrie,
    result: DFAResult,
) -> None:
    try:
        t0 = time.perf_counter()
        expr = fl.Expression(pattern, vocabulary, toktrie)
        t1 = time.perf_counter()

        result.build_times_ms.append((t1 - t0) * 1000)
        result.memory_usages.append(expr.memory_usage())
    except Exception:
        result.failures += 1

        return

    start_node = 0
    transitions: NDArray[np.uint64] = np.array([], dtype=np.uint64)

    t0 = time.perf_counter()

    for _ in range(NUM_SCAN_ITERS):
        transitions = expr.transitions(start_node)

    t1 = time.perf_counter()

    result.scan_times_us.append((t1 - t0) / NUM_SCAN_ITERS * 1_000_000)

    if transitions.size > 0:
        token_ids = transitions.tolist()

        random.seed(42)

        sample_ids = [token_ids[random.randint(0, len(token_ids) - 1)] for _ in range(min(10, len(token_ids)))]

        t0 = time.perf_counter()

        for _ in range(NUM_LOOKUP_ITERS):
            for tid in sample_ids:
                expr.next(start_node, int(tid))

        t1 = time.perf_counter()

        total_lookups = NUM_LOOKUP_ITERS * len(sample_ids)

        result.lookup_times_us.append((t1 - t0) / total_lookups * 1_000_000)
    else:
        result.lookup_times_us.append(0.0)


def avg(values: list[float]) -> float:
    if not values:
        return 0.0

    return sum(values) / len(values)


def print_single_leaderboard(
    title: str,
    results: list[DFAResult],
    value_fn: callable,
    unit: str,
) -> None:
    col_name = 20
    col_val = 12

    sorted_results = sorted(results, key=lambda r: value_fn(r))

    header = f"{'DFA Type':<{col_name}}{'Avg (' + unit + ')':>{col_val}}"
    sep = "-" * len(header)

    print(f"{title}:")
    print(sep)
    print(header)
    print(sep)

    for i, r in enumerate(sorted_results):
        print(
            f"{'#' + str(i + 1) + ' ' + r.name:<{col_name}}"
            f"{value_fn(r):>{col_val}.3f}"
        )

    print(sep)
    print()


def print_leaderboard(results: list[DFAResult]) -> None:
    print()

    print_single_leaderboard(
        "LOOKUP LEADERBOARD", results,
        lambda r: avg(r.lookup_times_us), "us",
    )

    print_single_leaderboard(
        "SCAN LEADERBOARD", results,
        lambda r: avg(r.scan_times_us), "us",
    )

    print_single_leaderboard(
        "BUILD LEADERBOARD", results,
        lambda r: avg(r.build_times_ms), "ms",
    )

    print_single_leaderboard(
        "MEMORY LEADERBOARD", results,
        lambda r: avg([float(m) for m in r.memory_usages]) / 1024, "KB",
    )


def main() -> None:
    print("Loading vocabulary...")

    try:
        vocabulary = fl.Vocabulary.from_file_path("../vocabulary.tiktoken", 1, 32)
    except Exception:
        print("Error: vocabulary.tiktoken not found.")

        return

    eos_id = vocabulary.get_eos_id()
    total_cases = NUM_ROUNDS * len(PATTERNS)

    print(f"Vocabulary loaded (eos_id={eos_id})")
    print(f"Building TokTrie bases for all {len(DFA_CONFIGS)} DFA types...")

    toktries: dict[int, fl.TokTrie] = {}

    for name, dfa_type in DFA_CONFIGS:
        t0 = time.perf_counter()
        toktries[dfa_type] = fl.TokTrie(vocabulary, dfa_type, 32, 32)
        t1 = time.perf_counter()

        print(f"  {name} TokTrie built in {(t1 - t0) * 1000:.1f} ms")

    print(f"\nRunning benchmark: {len(PATTERNS)} patterns x {len(DFA_CONFIGS)} DFA types x {NUM_ROUNDS} rounds")
    print(f"Cases per DFA type: {total_cases} (total_cases % {NUM_ROUNDS} == {total_cases % NUM_ROUNDS})")
    print(f"Scan iterations per case: {NUM_SCAN_ITERS}")
    print(f"Lookup iterations per case: {NUM_LOOKUP_ITERS}")
    print()

    results: list[DFAResult] = [DFAResult(name=name) for name, _ in DFA_CONFIGS]

    for r in range(NUM_ROUNDS):
        for i, pattern in enumerate(PATTERNS):
            idx = r * len(PATTERNS) + i + 1

            print(f"\r[{idx:5d}/{total_cases}] Round {r + 1}/{NUM_ROUNDS} - Pattern: {pattern[:50]:<50s}", end="", flush=True)

            for j, (name, dfa_type) in enumerate(DFA_CONFIGS):
                benchmark_expression(pattern, vocabulary, toktries[dfa_type], results[j])

    print("\n\nBenchmark complete!")

    print_leaderboard(results)


if __name__ == "__main__":
    main()
