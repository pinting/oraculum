# oraculum

Text to SQL LLM enforcement research.

**Warning:** This is a proof of concept & work in progress project, currently at the experimenting stage!

## Setup

Have [Rust](https://rustup.rs) and [UV](https://docs.astral.sh/uv/getting-started/installation) installed!

```bash
# Main project

uv venv --python 3.11
source .venv/bin/activate
make install
make run
```

## Experiments

Regular expression used: `(monday|tuesday|wednesday|thursday|friday)+`!
With the following token selection: `we -> d -> ne -> s -> day`!
Gemma 3 vocabulary is used!

### 1st - Ahead-of-time lattice building for constants using the Aho-Corasick algorithm

Token lattice approach for breaking up text into a Directed Acyclic Graph (forming all possible routes to build the text using the given vocabulary). The initial (one-time) build time (against the vocabulary) takes 2.23 s with extremely fast lattice construction (e.g. 92.501 µs for `It has snowed a lot in Europe`) and between 3-10 µs to traverse in the DAG. **No regular expression support**, but good for constant values!

### 2nd - Just-in-time lattice generation using only `guidance-ai/derivre`

Pure regex-based matching with derivative automata. 257 µs build time for the example regular expression. Slow next token filtering because of the exhaustive token matching, around 39 ms per step.

### 3rd - Just-in-time lattice generation using `microsoft/toktrie` and `guidance-ai/derivre`

Hybrid approach combining derivre and toktrie. 403 ms trie building (one time for a given vocabulary), 330 µs build time for the example regular expression. Moderate efficiency through trie pruning, 200-500 µs per step. Its weakness is the still relatively high transition attempts compared to AOT-based methods.

### 4th - Ahead-of-time lattice building for regular expressions using `dottxt-ai/outlines-core`

Prebuilt-based regex matching with precomputed token patterns. The obvious weakness are the increased memory usage for storing the index and the higher upfront cost: 211.950862 ms vocabulary rebuild (one time) and 1.190878411 s index build for the example regular expression. Its strength is its exceptional runtime efficiency, 6-18 µs per step.

### 5th - Ahead-of-time lattice building for regular expressions using `regex-automata` directly

Same as `outlines-core`. The `Index::new` function of Outlines is using linear search to build a token DFA on top of the regular expression byte DFA of `regex-automata`. This strategy is slow, could be improved - and it makes no sense to depend on a library which wraps another library in a couple of hundreds of lines. 583.171892 ms index build time for the example regular expression, 6-18 µs per step. The unanswered question, why build time decreased so much when using the same regular expression engine behind the scenes - perhaps it is due to no memory copy has to be initiated, the same vocabulary data structure is used as it is.

### 6th - Ahead-of-time lattice building for regular expressions using `microsoft/toktrie` and `guidance-ai/derivre`

The combination of AOT index building with TokTrie - Derivre: faster build time, same number of token matching per step as Outlines. 399.975656 ms trie building time (needed only once for a given vocabulary), 4.334894 ms index building time for the example regular expression and 7-21 µs per step.

### 7th - Performance comparisons between double HashMap / CSR continuous vector / hybrid approach

The benchmarks demonstrate a distinct space-time trade-off where the HybridDFA achieves the fastest performance for both lookups and scanning but requires the largest memory allocation due to its dual data structure approach. In contrast, the FlatDFA is the most memory-efficient option and maintains competitive scan speeds, though its binary search lookup mechanism causes performance to degrade significantly as the density of links increases. Ultimately, the DoubleHashDFA (the implementation `outlines-core` uses) proves to be the least effective implementation, consistently suffering from the slowest scan times while offering no distinct advantage in lookup speed or memory usage compared to the other architectures.

```
Benchmarking with nodes_count = 2000, links_count = 10000, vocabulary_size = 256000, lookup_count = 100000, scan_count = 100000

Lookup placements:
	HybridDFA - 30.546402ms
	DoubleHashDFA - 39.001341ms
	FlatDFA - 70.799119ms

Scan placements:
	HybridDFA - 5.33641904s
	FlatDFA - 5.411008303s
	DoubleHashDFA - 16.131345855s

Memory placements:
	FlatDFA - 152.59175 MB
	DoubleHashDFA - 191.52591 MB
	HybridDFA - 267.76512 MB
```

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

The AGPL-3.0 is a strong copyleft license that requires you to release the source code of any modified versions of this software, including when used over a network.