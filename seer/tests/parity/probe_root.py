"""Drive a `Root` implementation over the shared cases and dump a JSON trace.

Run with the experiment's interpreter it exercises the SageMath original; run
with this project's it exercises the BDD port. `tests/test_experiment_parity.py`
compares the two.
"""

import json
import sys

MODE = sys.argv[1]

if MODE == "experiment":
    sys.path.insert(0, "/home/pinting/repos/oraculum/experiments/9-advanced-modelling")

    from root import Root
else:
    from src.root import Root

from cases import ROOT_CASES

def run() -> list[list[dict]]:
    traces: list[list[dict]] = []

    for schema, ops in ROOT_CASES:
        resolver = Root(schema)
        trace: list[dict] = []

        for kind, name in ops:
            if MODE == "experiment":
                try:
                    resolver.use_field(name) if kind == "field" else resolver.use_table(name)
                    applied = True
                except Exception:
                    applied = False
            else:
                applied = (
                    resolver.use_field(name) if kind == "field" else resolver.use_table(name)
                )

            trace.append({
                "op": [kind, name],
                "applied": bool(applied),
                "fields": sorted(resolver.get_fields()),
                "required": sorted(resolver.get_required_tables()),
                "excluded_tables": sorted(resolver.get_excluded_tables()),
                "excluded_fields": sorted(resolver.get_excluded_fields()),
                "satisfied": bool(resolver.is_satisfied()),
            })

        traces.append(trace)

    return traces

print(json.dumps(run()))
