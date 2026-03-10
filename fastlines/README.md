# fastlines

Directed graph generator library for LLM token guidance. Translates regular expressions and constant strings to DFAs, inheriting the AOT data structure of `outlines-core` with further optimizations.

**Lattices** convert constant strings into DAGs using the Aho-Corasick algorithm with extremely fast construction.

**Expressions** convert regular expressions into DFAs using TokTrie with derivative automata.

```
Vocabulary loaded in 106.719618ms
Lattice base (AhoCorasick) built in 341.108908ms
Expression base (TokTrie) built in 160.463326ms
Creating indexes...
Lattice 'Why ' created in 17.18µs
Expression 'monday|tuesday|wednesday|thursday|friday' created in 286.292µs
Lattice '?' created in 2.31µs
Memory usage: 128 bytes
Memory usage: 787 bytes
Memory usage: 80 bytes
Routes: `Why` `Wh` `W` `W` 
> Why
Current: Why
Routes: ` ` ` ` 
>  
Current: Why 
Routes: `f` `m` `t` `w` `th` `we` `fr` `mo` `mon` `tu` `mond` `thur` `wed` `fri` `thu` `frid` `friday` `monday` `t` `m` `f` `w` 
> mon
Current: Why mon
Routes: `d` `day` `da` `d` 
> day
Current: Why monday
Routes: `?` `?` 
> ?
Current: Why monday?
```

## Setup

### Python API

Requires [Rust](https://rustup.rs) and [UV](https://docs.astral.sh/uv/getting-started/installation).

```bash
make build
source .venv/bin/activate
python example.py
```

The Python bindings fix both `N` (node index) and `T` (token ID) types to `u32` and use `FlatDFA` as the default DFA backend. The library can be rebuilt with different `N` / `T` / `D` configurations, but (at the moment) the source code needs to be modified for it (in the top of `pyvocabulary.rs` / `pyexpression.rs` / `pylattice.rs`).

```python
import fastlines_typed as fl

vocabulary = fl.Vocabulary.from_file_path("vocabulary.tiktoken", 1)

ac_base = fl.AhoCorasick(vocabulary)
lattice = fl.Lattice("hello", vocabulary, ac_base)

toktrie = fl.TokTrie(vocabulary)
expression = fl.Expression("mon|tue|wed", vocabulary, toktrie)
```

See the `example.py` for API details!

### Rust API

Only requires [Rust](https://rustup.rs).

```bash
cargo run --bin example
```

See the `example.rs` for API details!

## Benchmark

```bash
cargo run --bin benchmark --release
```

```
LOOKUP LEADERBOARD:
--------------------------------
DFA Type                Avg (us)
--------------------------------
#1 FastHashDFA             0.001
#2 DoubleHashDFA           0.003
#3 FlatDFA                 0.005
--------------------------------

SCAN LEADERBOARD:
--------------------------------
DFA Type                Avg (us)
--------------------------------
#1 FlatDFA                 0.235
#2 FastHashDFA             0.237
#3 DoubleHashDFA           4.787
--------------------------------

BUILD LEADERBOARD:
--------------------------------
DFA Type                Avg (ms)
--------------------------------
#1 DoubleHashDFA           1.698
#2 FastHashDFA             1.983
#3 FlatDFA                 2.011
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
