"""Parity with `experiments/9-advanced-modelling`.

Both sides now evaluate on the same SageMath structures, so what these tests
check is the port's wrapper rather than the mathematics: the bool returns that
replaced the experiment's exceptions, the sorted results that replaced its
sets, and the `copy()` semantics, all driven over the same cases with their
traces compared step for step.

They skip unless the experiment's own virtualenv is present.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT: Path = Path(__file__).parent.parent
EXPERIMENT: Path = PROJECT.parent / "experiments" / "9-advanced-modelling"
EXPERIMENT_PYTHON: Path = EXPERIMENT / ".venv" / "bin" / "python"
PARITY: Path = Path(__file__).parent / "parity"

TIMEOUT: int = 600

def _has_sage() -> bool:
    if not EXPERIMENT_PYTHON.exists():
        return False

    probe = subprocess.run(
        [str(EXPERIMENT_PYTHON), "-c", "import sage"],
        capture_output=True,
        timeout=TIMEOUT,
    )

    return probe.returncode == 0

requires_experiment = pytest.mark.skipif(
    not _has_sage(),
    reason="the SageMath backed experiment venv is not available",
)

def _run(interpreter: Path, probe: str, mode: str, cwd: Path) -> object:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join([str(PARITY), str(cwd)])

    result = subprocess.run(
        [str(interpreter), str(PARITY / probe), mode],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=environment,
        timeout=TIMEOUT,
    )

    assert result.returncode == 0, result.stderr[-2000:]

    return json.loads(result.stdout)

@requires_experiment
def test_root_matches_the_experiment() -> None:
    """The wrapped `Root` resolves exactly like the experiment's original."""

    expected = _run(EXPERIMENT_PYTHON, "probe_root.py", "experiment", EXPERIMENT)
    actual = _run(Path(sys.executable), "probe_root.py", "port", PROJECT)

    assert len(actual) == len(expected)

    for index, (want, got) in enumerate(zip(expected, actual)):
        assert got == want, f"case {index} diverged"

@requires_experiment
def test_join_graph_matches_the_experiment() -> None:
    """`JoinGraph` traverses and merges like the experiment's raw `Graph`."""

    expected = _run(EXPERIMENT_PYTHON, "probe_graph.py", "experiment", EXPERIMENT)
    actual = _run(Path(sys.executable), "probe_graph.py", "port", PROJECT)

    assert actual == expected
