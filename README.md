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

### 1st - Ahead-of-time lattice building for constants using the Aho-Corasick algorithm

Token lattice approach for breaking up text into a Directed Acyclic Graph (forming all possible routes to build the text using the given vocabulary). The initial (one-time) build time (against the vocabulary) takes 2.23 s with extremely fast lattice construction (102 µs for 16 characters). **No regular expression support**, but good for constant values.

### 2nd - Just-in-time lattice generation using only `guidance-ai/derivre`

Pure regex-based matching with derivative automata. 252 µs build time for a small regular expression. Slow next token filtering because of the exhaustive token matching (255k matches per step).

### 3rd - Just-in-time lattice generation using `microsoft/toktrie` and `guidance-ai/derivre`

Hybrid approach combining derivre and toktrie. 411 µs trie building (one time for a given vocabulary), 260 µs build time for a single small regular expression. Moderate efficiency through trie pruning (300-600 matches per step). Its weakness is the still relatively high transition attempts compared to AOT-based methods.

### 4th - Ahead-of-time lattice building for regular expressions using `dottxt-ai/outlines-core`

Prebuilt-based regex matching with precomputed token patterns. Its strength is its exceptional runtime efficiency (1-30 matches per step). The obvious weakness is the higher upfront cost (1.12 s index build) and increased memory usage for storing the index.

### 5th - Ahead-of-time lattice building for regular expressions using `regex-automata` directly

Same as `outlines-core`. The `Index::new` function of Outlines is using linear search to build a token DFA on top of the regular expression byte DFA of `regex-automata`. This strategy is slow, could be improved - and it makes no sense to depend on a library which wraps another library in a couple of hundreds of lines. 614 ms building time for a small regular expression. The unanswered question, why build time decreased so much when using the same regular expression engine behind the scenes - perhaps it is due to no memory copy has to be initiated, the same vocabulary data structure is used as it is.

### 6th - Ahead-of-time lattice building for regular expressions using `microsoft/toktrie` and `guidance-ai/derivre`

The combination of AOT index building with TokTrie - Derivre: faster build time, same number of token matching per step as Outlines. 408 ms trie building time (needed only once for a given vocabulary), 3.4 ms index building time for a small regular expressions.

### 7th - Performance comparison between HashMap - nested HashMap - CSR continuous vector as DFA data structure



## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

The AGPL-3.0 is a strong copyleft license that requires you to release the source code of any modified versions of this software, including when used over a network.