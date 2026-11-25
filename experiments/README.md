# Experiments

Research prototypes evaluating token-level automata, DFA data structures, and semantic constraint solvers used in `kernel` and `seer`.

## 1. Ahead-of-time constants with Aho-Corasick

[`1-aot-ahocorasick`](1-aot-ahocorasick/README.md)

Breaks a constant string into a directed acyclic graph of all possible token paths under the vocabulary. Initial setup takes 2.3 s, building a lattice takes roughly 80 µs, and traversing the DAG takes 3 to 10 µs per step. Does not support regular expressions, but works well for constant strings.

## 2. Just-in-time regular expressions with derivre

[`2-jit-derivre`](2-jit-derivre/README.md)

Tests pure regex matching with derivative automata over the Gemma 3 vocabulary. Compiling the example regular expression takes 257 µs, while filtering the next token checks every vocabulary token exhaustively and takes around 39 ms per step.

## 3. Just-in-time regular expressions with toktrie and derivre

[`3-jit-toktrie-derivre`](3-jit-toktrie-derivre/README.md)

Combines `derivre` with `toktrie` for sublinear prefix-trie filtering. Building the trie takes 403 ms once per vocabulary, compiling the example pattern takes 330 µs, and trie pruning drops step times to 200 to 500 µs.

## 4. Ahead-of-time regular expressions with outlines-core

[`4-aot-outlines`](4-aot-outlines/README.md)

Precomputes token patterns for regex matching using `outlines-core`. Preparing the vocabulary takes 212 ms once, compiling the example pattern takes 1.19 s, and step time drops to 6 to 18 µs.

## 5. Ahead-of-time regular expressions with regex-automata

[`5-aot-regex-automata`](5-aot-regex-automata/README.md)

Calls `regex-automata` directly without `outlines-core` wrapper overhead and reuses the vocabulary structure without extra copies. Index construction for the example pattern drops to 583 ms, while step times remain 6 to 18 µs.

## 6. Ahead-of-time regular expressions with toktrie and derivre

[`6-aot-toktrie-derivre`](6-aot-toktrie-derivre/README.md)

Combines ahead-of-time index compilation with `toktrie` and `derivre`. Initial trie generation takes 400 ms once per vocabulary, building the example index takes 4.33 ms, and step evaluation takes 7 to 21 µs while matching the same token count per step as Outlines.

## 7. DFA data structure benchmarks

[`7-dfa-performance-test`](7-dfa-performance-test/README.md)

Compares `FastHashDFA`, `DoubleHashDFA`, and `FlatDFA` on lookup speed, transition scanning, build time, and memory usage. `FlatDFA` wins on scan performance and memory footprint because continuous memory reads benefit from CPU caching, making it the default DFA backend in `kernel`.

## 8. Namespace resolution with BDDs

[`8-bdd`](8-bdd/README.md)

Resolves global and per-alias field namespaces in Rust using binary decision diagrams (`boolean_expression`) for unqualified fields and set intersection for aliased scopes.

## 9. Namespace and table relation resolution with ZDDs and graphs

[`9-zdd-graphs`](9-zdd-graphs/README.md)

Extends `Context` in Python using SageMath to add schema parsing, a GF(2) `BooleanPolynomialRing` over ZDDs for field conflicts, and foreign-key graph contraction (`merge_vertices`) for `FROM` and `JOIN` resolution. `seer` adopts this approach.
