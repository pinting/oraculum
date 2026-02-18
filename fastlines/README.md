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
Loading vocabulary...
Vocabulary loaded (eos_id=1)
Building TokTrie bases for all 3 DFA types...
  FastHashDFA TokTrie built in 412.9 ms
  DoubleHashDFA TokTrie built in 373.4 ms
  FlatDFA TokTrie built in 374.9 ms

Running benchmark: 100 patterns x 3 DFA types x 100 rounds
Cases per DFA type: 10000 (total_cases % 100 == 0)
Scan iterations per case: 50
Lookup iterations per case: 200

[10000/10000] Round 100/100 - Pattern: (inter|intra|extra|ultra|super|hyper)(nation|state

Benchmark complete!

LOOKUP LEADERBOARD:
--------------------------------
DFA Type                Avg (us)
--------------------------------
#1 FastHashDFA             0.988
#2 FlatDFA                 1.055
#3 DoubleHashDFA           1.120
--------------------------------

SCAN LEADERBOARD:
--------------------------------
DFA Type                Avg (us)
--------------------------------
#1 FastHashDFA            21.800
#2 FlatDFA                22.466
#3 DoubleHashDFA          77.816
--------------------------------

BUILD LEADERBOARD:
--------------------------------
DFA Type                Avg (ms)
--------------------------------
#1 DoubleHashDFA          16.379
#2 FastHashDFA            19.187
#3 FlatDFA                24.214
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
