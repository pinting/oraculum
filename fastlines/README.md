# `fastlines`

Directed graph generator library for LLM token guidance. Translates regular expressions and constant strings to DFAs, inheriting the AOT data structure of `outlines-core` with optimizations from `llguidance` and a custom `FastHashDFA` found in Experiment 7.

**Lattices** convert constant strings into DAGs using the Aho-Corasick algorithm with extremely fast construction.

**Expressions** convert regular expressions into DFAs using TokTrie with derivative automata.

## Setup

Requires [uv](https://github.com/astral-sh/uv).

```bash
./setup.sh
source .venv/bin/activate
python main.py # Example application
```

## Benchmark

```
LOOKUP LEADERBOARD:
--------------------------------
DFA Type                Avg (us)
--------------------------------
#1 FastHashDFA             0.986
#2 FlatDFA                 1.052
#3 DoubleHashDFA           1.122
--------------------------------

SCAN LEADERBOARD:
--------------------------------
DFA Type                Avg (us)
--------------------------------
#1 FastHashDFA            22.195
#2 FlatDFA                24.587
#3 DoubleHashDFA          79.970
--------------------------------

BUILD LEADERBOARD:
--------------------------------
DFA Type                Avg (ms)
--------------------------------
#1 DoubleHashDFA          17.900
#2 FastHashDFA            20.871
#3 FlatDFA                26.033
--------------------------------

MEMORY LEADERBOARD:
--------------------------------
DFA Type                Avg (KB)
--------------------------------
#1 FlatDFA               120.275
#2 DoubleHashDFA         208.841
#3 FastHashDFA           284.461
--------------------------------
```

## License

This project is licensed under the [GNU Affero General Public License v3.0](../LICENSE).
