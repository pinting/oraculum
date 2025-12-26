# oraculum

Text to SQL LLM enforcement research.

**Warning:** This is a proof of concept and work in progress, currently at the experimenting stage!

## Setup

Have [Rust](https://rustup.rs) and [UV](https://docs.astral.sh/uv/getting-started/installation) installed!

```bash
# Main project

uv venv --python 3.11
source .venv/bin/activate
make install
make run

# Experiments

cd experiments/ahocorasick && cargo run
cd experiments/derivre && cargo run
cd experiments/outlines && cargo run
cd experiments/toktrie && cargo run
```

## Experiments

Four constrained generation approaches were tested using the Gemma 3 vocabulary:

- **Aho-Corasick**: Token lattice approach for breaking up text into a Directed Acyclic Graph (forming all possible routes to build the text using the given vocabulary). The initial (one-time) build time (against the vocabulary) takes 2.23 s with extremely fast lattice construction (102 µs for 16 characters). Obviously no regular expression support, but good for constant values!
- **derivre**: Pure regex-based matching with derivative automata. Slow because of the exhaustive token matching (255k matches per step).
- **toktrie**: Hybrid approach combining derivre and toktrie. 261 µs build time and moderate efficiency through trie pruning (300-600 matches per step). Its weakness is the still relatively high transition attempts compared to index-based methods.
- **outlines**: Index-based regex matching with precomputed token patterns. Its strength is its exceptional runtime efficiency (1-18 matches per step). The obvious weakness is the higher upfront cost (1.12s index build) and increased memory usage for storing the index.

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

The AGPL-3.0 is a strong copyleft license that requires you to release the source code of any modified versions of this software, including when used over a network.