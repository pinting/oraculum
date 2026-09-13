"""The modelling layer, timed.

`main.py` times nothing - it asks whether the engine behaves - and an end to
end run answers the wrong question anyway: most of it is the kernel masking a
262k vocabulary, and the modelling is a few percent of a corpus run over a
three table schema. So this times the modelling on its own, on schemas wide
enough for the shape of the cost to show.

Two halves, one per structure in `backend.py`:

* the algebra, over a schema's real field constraints - build, select, and the
  four queries a selection invalidates;
* the join graph, isolated from `Relationships` so that what is measured is
  copy, contraction and incidence rather than `_build_edges`.

Read the two rows that scale with the schema - `nonzero` and the contraction
chain. Those are the ones a branch of the syntax graph pays; building the ring
and building the graph happen once per schema.

    python tests/benchmark.py
    python tests/benchmark.py --rounds 5000
"""

from __future__ import annotations

import argparse
import itertools
import random
import sys
import time
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend import Algebra, JoinGraph

NAME_WIDTH: int = 26
VALUE_WIDTH: int = 11

def schema(tables: int, columns: int, seed: int = 7) -> dict[str, list[str]]:
    """A `table -> columns` map where names are shared across tables.

    Sharing is the whole point: a name living in `k` tables is what the mutual
    exclusion constraint is over, and `id` lives in all of them.
    """

    rnd = random.Random(seed)
    built: dict[str, list[str]] = {}

    for table in range(tables):
        names: list[str] = ["id"]

        for column in range(columns):
            names.append(f"col{column % (columns // 2 + 1)}_{table % 3}")

        for other in range(max(0, table - 2), table):
            names.append(f"t{other}_id")

        built[f"t{table}"] = names

    return built

def clock(rounds: int, body) -> float:
    """Microseconds per round, after one warm up round."""

    body(1)

    start: float = time.perf_counter()

    body(rounds)

    return (time.perf_counter() - start) / rounds * 1e6

def algebra_rows(tables: dict[str, list[str]], rounds: int) -> dict[str, float]:
    names: list[str] = sorted(tables)
    by_field: dict[str, set[str]] = {}

    for table, fields in tables.items():
        for field in fields:
            by_field.setdefault(field, set()).add(table)

    algebra = Algebra(names)
    constraints = {
        field: algebra.mutual_exclusion(sorted(owners))
        for field, owners in sorted(by_field.items())
    }
    polys = tuple(constraints.values())
    fields = sorted(constraints)
    rnd = random.Random(5)
    order = [rnd.choice(fields) for _ in range(rounds + 1)]

    # A selection two fields deep, which is where a real query spends its time.
    settled = algebra.product(
        algebra.product(algebra.one(), constraints[fields[0]]),
        constraints[fields[len(fields) // 2]],
    )

    def build(k: int) -> None:
        for _ in range(k):
            fresh = Algebra(names)

            for field, owners in by_field.items():
                fresh.mutual_exclusion(sorted(owners))

    def product(k: int) -> None:
        for index in range(k):
            algebra.product(settled, constraints[order[index]])

    def nonzero(k: int) -> None:
        for _ in range(k):
            algebra.nonzero(settled, polys)

    def viable(k: int) -> None:
        for _ in range(k):
            algebra.viable(settled)

    def settled_queries(k: int) -> None:
        for _ in range(k):
            algebra.is_zero(settled)
            algebra.holds_empty(settled)
            algebra.constrained(settled)

    return {
        "build the ring": clock(max(rounds // 50, 1), build),
        "product": clock(rounds, product),
        "nonzero (all fields)": clock(max(rounds // 5, 1), nonzero),
        "viable (all tables)": clock(rounds, viable),
        "is_zero+holds+support": clock(rounds, settled_queries),
    }

def graph_rows(vertices: int, rounds: int, seed: int = 3) -> dict[str, float]:
    rnd = random.Random(seed)
    names: list[str] = [f"v{index}" for index in range(vertices)]
    edges: list[tuple[str, str, object]] = [
        (source, target, (source, target))
        for source, target in itertools.combinations(names, 2)
        if rnd.random() < 0.4
    ]

    base = JoinGraph(edges)

    def construct(k: int) -> None:
        for _ in range(k):
            JoinGraph(edges)

    def copy(k: int) -> None:
        for _ in range(k):
            base.copy()

    def incident(k: int) -> None:
        for _ in range(k):
            base.copy().edges(names[0])

    def contract(k: int) -> None:
        for _ in range(k):
            graph = base
            head: str = names[0]

            for other in names[1:6]:
                graph = graph.copy()
                graph.merge_vertices(head, other)
                graph.edges(head)

    return {
        "construct": clock(max(rounds // 10, 1), construct),
        "copy": clock(rounds, copy),
        "copy + edges(head)": clock(rounds, incident),
        "copy/contract chain of 5": clock(max(rounds // 5, 1), contract),
    }

def report(title: str, rows: dict[str, float]) -> None:
    print(f"\n{title}")

    for label, value in rows.items():
        print("  " + f"{label:<{NAME_WIDTH}}" + f"{value:>{VALUE_WIDTH}.2f}")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--rounds", type=int, default=20000)

    arguments = parser.parse_args()

    print("Microseconds per operation.")

    for tables, columns in ((3, 6), (8, 8), (16, 10)):
        shape = schema(tables, columns)
        fields = len({name for columns in shape.values() for name in columns})

        report(
            f"algebra - {tables} tables, {fields} distinct field names",
            algebra_rows(shape, arguments.rounds),
        )

    for vertices in (6, 12, 24):
        report(
            f"join graph - {vertices} vertices",
            graph_rows(vertices, arguments.rounds),
        )

    return 0

if __name__ == "__main__":
    sys.exit(main())
