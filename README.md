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

Token lattice approach for breaking up text into a Directed Acyclic Graph (forming all possible routes to build the text using the given vocabulary). The initial (one-time) build time (against the vocabulary) takes 2.3 s with extremely fast lattice construction (e.g. 80 µs for `It has snowed a lot in Europe`) and between 3-10 µs to traverse in the DAG. **No regular expression support**, but good for constant values!

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

### 7th - Performance comparisons between `FastHashDFA` vs. `DoubleHashDFA` vs. `FlatDFA`

The benchmarks demonstrate a space-time trade-off where the flat structures achieves the fastest performance for scanning and hash structures for lookups; while hybrid solutions are the fastest, they require the largest memory allocation. Ultimately, the `DoubleHashDFA` (the implementation `outlines-core` uses) proves to be a good universal solution, average in both lookups and scans, but only suffering (worst case) 2x memory usage compared to `FlatDFA` which is the most compact, but having a slow lookup algorithm due to its linearity (optimized by binary tree search on a CSR data structure, but still lacking the jump capabilities of hash functions).

The heavily optimized `FastHashDFA` tries to combine both of the two worlds and outperforms other candidates in lookup and scan speeds, but suffers a memory explosion after 15k links.

```
Nodes: 200 | Links: 25 - 75

Lookup: 5.99ms (2.04x FlatDFA / 3.23x DoubleHashDFA)
Scan: 36.94ms (0.99x FlatDFA / 4.35x DoubleHashDFA)
Memory: 170% of FlatDFA / 92% of DoubleHashDFA

Nodes: 200 | Links: 50 - 150

Lookup: 6.19ms (2.17x FlatDFA / 3.23x DoubleHashDFA)
Scan: 67.48ms (0.99x FlatDFA / 4.35x DoubleHashDFA)
Memory: 195% of FlatDFA / 110% of DoubleHashDFA

Nodes: 2,000 | Links: 50 - 1,000

Lookup: 14.62ms (1.75x FlatDFA / 2.04x DoubleHashDFA)
Scan: 337.53ms (1.00x FlatDFA / 4.17x DoubleHashDFA)
Memory: 190% of FlatDFA / 111% of DoubleHashDFA

Nodes: 2,000 | Links: 500 - 1,500

Lookup: 18.73ms (1.69x FlatDFA / 1.72x DoubleHashDFA)
Scan: 641.35ms (1.00x FlatDFA / 4.17x DoubleHashDFA)
Memory: 201% of FlatDFA / 119% of DoubleHashDFA

Nodes: 2,000 | Links: 5,000 - 15,000

Lookup: 25.75ms (2.63x FlatDFA / 1.54x DoubleHashDFA)
Scan: 6.39s (1.00x FlatDFA / 4.17x DoubleHashDFA)
Memory: 191% of FlatDFA / 121% of DoubleHashDFA

Nodes: 2,000 | Links: 25,000 - 75,000

Lookup: 35.28ms (2.94x FlatDFA / 1.27x DoubleHashDFA)
Scan: 31.81s (1.00x FlatDFA / 4.17x DoubleHashDFA)
Memory: 293% of FlatDFA / 167% of DoubleHashDFA
```

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

The AGPL-3.0 is a strong copyleft license that requires you to release the source code of any modified versions of this software, including when used over a network.