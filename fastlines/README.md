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

## DFA Backends

| Backend | Lookup | Scan | Memory |
|---|---|---|---|
| `FAST_HASH_DFA` | Fastest | Fastest | Moderate - Highest (after 15k links) |
| `DOUBLE_HASH_DFA` | Balanced | Balanced | Moderate |
| `FLAT_DFA` | Slowest | Fastest | Lowest |

All backends support configurable 16, 32, and 64-bit unit sizes for nodes, tokens, and offsets.

## License

This project is licensed under the [GNU Affero General Public License v3.0](../LICENSE).
