"""The two modelling primitives against a brute force reference.

`main.py` runs the corpus and asserts the engine behaves, which exercises the
algebra and the graph only where the corpus happens to go. This asserts they
are the objects they claim to be, on inputs no schema would produce.

The reference is written here, in the most obvious way there is, and shares
nothing with what it checks:

* a boolean function is the **set of assignments it is true on**, so `product`
  is set intersection and "exactly one of these tables" is a comprehension over
  every assignment. The kernel holds the same function as a polynomial in a
  decision diagram, which is a representation away from this one in every
  respect - and its `constrained` reads the polynomial's support where the
  reference reads functional dependence, which agree only if the diagram really
  is the algebraic normal form;
* a contracted multigraph is a **dict of classes**, rebuilt from scratch after
  every merge, against an array of representatives layered over shared edges.

Small, since the reference enumerates `2^n` assignments - but the disagreements
that matter show up at four variables, not at forty.

    python tests/model.py
    python tests/model.py --verbose
    python tests/model.py --trials 2000

The exit status is the number of disagreements, capped at 125, so `make
test-all` fails the build when the port drifts from the reference.
"""

from __future__ import annotations

import argparse
import itertools
import random
import sys
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend import Algebra, JoinGraph

MAX_STATUS: int = 125

class Reference:
    """A boolean function as the set of assignments satisfying it.

    An assignment is a bit mask over the variables, so a function over `n` of
    them is a subset of `range(2 ** n)`. Nothing is clever and nothing is
    shared with the ring; that is the point.
    """

    def __init__(self, names: list[str]) -> None:
        self.names: list[str] = list(names)
        self.bits: dict[str, int] = {name: 1 << i for i, name in enumerate(names)}
        self.space: frozenset[int] = frozenset(range(1 << len(names)))

    def one(self) -> frozenset[int]:
        return self.space

    def mutual_exclusion(self, names: list[str]) -> frozenset[int]:
        mask: int = 0

        for name in names:
            mask |= self.bits[name]

        return frozenset(a for a in self.space if (a & mask).bit_count() == 1)

    def product(self, left: frozenset[int], right: frozenset[int]) -> frozenset[int]:
        return left & right

    def assume(self, poly: frozenset[int], name: str) -> frozenset[int]:
        """`f` with the variable pinned on, which leaves it free again."""

        bit: int = self.bits[name]

        return frozenset(a for a in self.space if (a | bit) in poly)

    def is_zero(self, poly: frozenset[int]) -> bool:
        return not poly

    def holds_empty(self, poly: frozenset[int]) -> bool:
        return 0 in poly

    def constrained(self, poly: frozenset[int]) -> frozenset[str]:
        """The variables the function's value actually depends on."""

        return frozenset(
            name
            for name, bit in self.bits.items()
            if any(((a | bit) in poly) != ((a & ~bit) in poly) for a in self.space)
        )

    def viable(self, poly: frozenset[int]) -> frozenset[str]:
        return frozenset(name for name in self.names if self.assume(poly, name))

    def nonzero(self, poly: frozenset[int], others: list[frozenset[int]]) -> tuple[bool, ...]:
        return tuple(bool(poly & other) for other in others)

class ReferenceGraph:
    """A contracted multigraph as the edge list plus a class per vertex."""

    def __init__(self, edges: list[tuple[str, str, object]]) -> None:
        self.edge_list = list(edges)
        self.classes: dict[str, set[str]] = {}

        for source, target, _ in self.edge_list:
            self.classes.setdefault(source, {source})
            self.classes.setdefault(target, {target})

    def copy(self) -> "ReferenceGraph":
        clone = ReferenceGraph.__new__(ReferenceGraph)

        clone.edge_list = self.edge_list
        clone.classes = {head: set(members) for head, members in self.classes.items()}

        return clone

    def _owner(self, vertex: str) -> str | None:
        for head, members in self.classes.items():
            if vertex in members:
                return head

        return None

    def __contains__(self, node: str) -> bool:
        return node in self.classes

    def nodes(self) -> list[str]:
        return sorted(self.classes)

    def edges(self, node: str) -> list[tuple[str, object]]:
        if node not in self.classes:
            return []

        incident: list[tuple[str, object]] = []

        for source, target, label in self.edge_list:
            left, right = self._owner(source), self._owner(target)

            if left == node and right != node:
                incident.append((right, label))
            elif right == node and left != node:
                incident.append((left, label))

        return incident

    def merge_vertices(self, head: str, other: str) -> None:
        if head == other or head not in self.classes or other not in self.classes:
            return

        self.classes[head] |= self.classes.pop(other)

class Report:
    """Counts, and the first few disagreements in full."""

    def __init__(self, verbose: bool) -> None:
        self.verbose: bool = verbose
        self.checks: int = 0
        self.failures: int = 0

    def check(self, question: str, expected, actual, history) -> None:
        self.checks += 1

        if expected == actual:
            return

        self.failures += 1

        if self.failures <= 10 or self.verbose:
            print(f"  {question}")
            print(f"    reference: {expected!r}")
            print(f"    kernel:    {actual!r}")
            print(f"    after:     {history}")

def algebra_trials(trials: int, report: Report, seed: int) -> None:
    """Random products of mutual exclusions, and every question `root.py` asks.

    The constraints are every non-empty subset of the tables, which covers the
    real ones - a field's constraint is the subset of tables it lives in - and
    a great many that no schema would produce.
    """

    for size in (2, 3, 4, 5):
        names: list[str] = [f"t{index}" for index in range(size)]
        subsets: list[list[str]] = [
            list(subset)
            for count in range(1, size + 1)
            for subset in itertools.combinations(names, count)
        ]

        algebra = Algebra(names)
        reference = Reference(names)

        constraints = [algebra.mutual_exclusion(subset) for subset in subsets]
        expected = [reference.mutual_exclusion(subset) for subset in subsets]

        rnd = random.Random(seed + size)

        for _ in range(trials):
            current, shadow = algebra.one(), reference.one()
            history: list[tuple[str, object]] = []

            for _ in range(rnd.randrange(1, 6)):
                if rnd.random() < 0.35:
                    table: str = rnd.choice(names)

                    history.append(("assume", table))

                    current = algebra.assume(current, table)
                    shadow = reference.assume(shadow, table)
                else:
                    choice: int = rnd.randrange(len(subsets))

                    history.append(("use", tuple(subsets[choice])))

                    current = algebra.product(current, constraints[choice])
                    shadow = reference.product(shadow, expected[choice])

                report.check("is_zero",
                             reference.is_zero(shadow), algebra.is_zero(current), history)
                report.check("holds_empty",
                             reference.holds_empty(shadow), algebra.holds_empty(current), history)
                report.check("constrained",
                             reference.constrained(shadow), algebra.constrained(current), history)
                report.check("viable",
                             reference.viable(shadow), algebra.viable(current), history)
                report.check("nonzero",
                             reference.nonzero(shadow, expected),
                             tuple(algebra.nonzero(current, constraints)), history)

                if reference.is_zero(shadow):
                    break

def graph_trials(trials: int, report: Report, seed: int) -> None:
    """Random multigraphs, contracted a vertex at a time, copied at every step."""

    for vertices, density in ((4, 0.6), (7, 0.35), (10, 0.25)):
        names: list[str] = [f"v{index}" for index in range(vertices)]
        rnd = random.Random(seed + vertices)

        for _ in range(trials):
            edges: list[tuple[str, str, object]] = []

            for source, target in itertools.combinations(names, 2):
                while rnd.random() < density:
                    edges.append((source, target, f"fk{len(edges)}"))

            graph, shadow = JoinGraph(edges), ReferenceGraph(edges)
            history: list[tuple[str, str]] = []

            for _ in range(vertices):
                # Every branch of the syntax graph copies before it looks, so
                # the copies are what is compared rather than the originals.
                graph, shadow = graph.copy(), shadow.copy()

                report.check("nodes", shadow.nodes(), graph.nodes(), history)
                report.check(
                    "membership",
                    tuple(node in shadow for node in names),
                    tuple(node in graph for node in names),
                    history,
                )
                report.check(
                    "edges",
                    tuple(tuple(sorted(shadow.edges(node))) for node in names),
                    tuple(tuple(sorted(graph.edges(node))) for node in names),
                    history,
                )

                head, other = rnd.sample(names, 2)

                history.append((head, other))

                graph.merge_vertices(head, other)
                shadow.merge_vertices(head, other)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--trials", type=int, default=200, help="trials per shape")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--verbose", action="store_true", help="print every disagreement")

    arguments = parser.parse_args()
    report = Report(arguments.verbose)

    algebra_trials(arguments.trials, report, arguments.seed)
    graph_trials(arguments.trials, report, arguments.seed)

    if report.failures:
        print(f"{report.failures} disagreements over {report.checks} comparisons")

        return min(report.failures, MAX_STATUS)

    print(f"{report.checks} comparisons, the kernel matched the reference")

    return 0

if __name__ == "__main__":
    sys.exit(main())
