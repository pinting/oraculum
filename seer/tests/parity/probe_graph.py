"""Drive a join graph over the shared walks and dump a JSON trace."""

import json
import sys

MODE = sys.argv[1]

if MODE == "experiment":
    sys.path.insert(0, "/home/pinting/repos/oraculum/experiments/9-advanced-modelling")

    from schema import parse_schema
    from relationships import Relationships
else:
    from src.schema import parse_schema
    from src.relationships import Relationships

from cases import JOIN_SCHEMA, REQUIRED, WALKS

class StubConflicts:
    """The slice of `Conflicts` the experiment's `Relationships` reads."""

    def __init__(self, required):
        self._required = set(required)

    def get_required_tables(self):
        return set(self._required)

    def get_excluded_tables(self):
        return set()

    def use_table(self, table):
        self._required.discard(table)

def build(schema, required):
    if MODE == "experiment":
        return Relationships(StubConflicts(required), schema)

    return Relationships(schema, required)

def neighbors(relationships):
    return sorted({n.table for n in relationships.get_joinable_neighbors()})

def run() -> list[dict]:
    schema = parse_schema(JOIN_SCHEMA)
    results: list[dict] = []

    for index, start, targets in WALKS:
        relationships = build(schema, REQUIRED[index])

        if MODE == "experiment":
            relationships.head = start
            nodes = sorted(str(v) for v in relationships.graph.vertices())
        else:
            relationships.use_table(start)
            nodes = relationships.graph.nodes()

        walk: dict = {"start": start, "nodes": nodes, "steps": []}

        for target in targets:
            before = neighbors(relationships)
            chosen = [n for n in relationships.get_joinable_neighbors() if n.table == target]

            if not chosen:
                walk["steps"].append({"target": target, "before": before, "joined": False})

                break

            if MODE == "experiment":
                relationships.graph.merge_vertices([relationships.head, target])
            else:
                relationships.join_table(chosen[0])

            walk["steps"].append({
                "target": target,
                "before": before,
                "joined": True,
                "after": neighbors(relationships),
            })

        results.append(walk)

    return results

print(json.dumps(run()))
