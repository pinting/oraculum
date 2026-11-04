# kernel

Directed graph generator library for LLM token guidance. Translates regular expressions and constant strings to DFAs, inheriting the ahead-of-time data structure from `outlines-core` with additional optimizations.

Lattices convert constant strings into DAGs using the Aho-Corasick algorithm for fast construction.

Expressions convert regular expressions into DFAs using TokTrie with derivative automata.

Groups handle subtraction: one inclusion pattern minus any number of exclusions, allowing an alias to represent any identifier that is not a reserved word.

On top of these indexes, the library provides a dynamic API: a factory that caches indexes and returns numeric identifiers, and a runner that maintains active index states across a worker pool. The caller maintains the graph topology; the kernel reports when an active head has completed and queries what should follow.

## Setup

Requires [Rust](https://rustup.rs) and [UV](https://docs.astral.sh/uv/getting-started/installation).

```bash
make build       # Build the kernel
make benchmark   # DFA data structure benchmarks
```

## Dynamic API

The dynamic API consists of two core components and a resolver callback:

`Factory` manages the index registry and returns identifiers rather than index references. An index is built at most once regardless of how many callers or threads request it simultaneously. This keeps heads lightweight because they borrow shared indexes rather than owning them.

`Runner` maintains the pool of active indexes, called heads. Each head consists of a `Memory` instance tracking position and consumed tokens, along with an opaque caller payload. Feeding a token advances every active head across the worker threads; heads that reject the token are discarded.

The resolver callback determines transitions. When a head reaches the end of its index, the runner calls the resolver with `(head_id, payload, matched)`. The resolver returns either `None` when generation terminates, or a list of `(spec, payload)` pairs describing successor indexes. These successors are instantiated on the worker pool and become the next active heads.

```python
import kernel as kl

vocabulary = kl.Vocabulary.from_file_path("../vocabulary.tiktoken", 1)
factory = kl.Factory(vocabulary)

# An alias: any identifier except a handful of words.
identifier = factory.expression("[a-zA-Z_][a-zA-Z0-9_]*")
reserved = [factory.lattice(word) for word in ("hello", "world")]
alias = factory.group(identifier, reserved)

runner = kl.Runner(factory, workers=4)

def resolve(head_id, payload, matched):
    if payload == "greeting":
        return [((("lattice", " ")), "space")]
    if payload == "space":
        return [(alias, "alias")]

    return None                      # The end of the graph

runner.set_resolver(resolve)
runner.spawn(("lattice", "hello"), "greeting")

while not runner.is_completed():
    token_id = pick(runner.routes())   # A custom sampler
    runner.feed(token_id)

print(runner.matched())
```

An index is specified either by its identifier or by its specification tuple:

```python
("lattice", "SELECT")                        # A constant string
("expression", "[a-zA-Z_][a-zA-Z0-9_]*")     # A regular expression
("group", include_id, [exclude_id, ...])     # Include minus the excludes
```

### Groups

A group accepts when its inclusion pattern accepts and none of its exclusions match. While an exclusion continues to match the consumed input, the group remains blocked: it does not report completion and removes the terminating token from its offered routes, requiring generation to continue.

```
hello    the inclusion accepts, but so does an exclusion  -> blocked
hello2   the `hello` exclusion died on the `2`            -> accepted
hell     no exclusion spells it                           -> accepted
```

Exclusions are anchored at the start of an identifier; once an exclusion rejects a token, it cannot match again and is removed from memory. Because of this early pruning, subtracting dozens of reserved words adds minimal overhead over evaluating the inclusion pattern alone.

Groups can also be nested on either side of an inclusion or exclusion.

### Memory and parallelism

Indexes store no traversal state. A `Lattice` is a table of token edges per byte offset, and an `Expression` is a DFA. Both are immutable once built. Traversal state is held in `Memory`, with one instance per head. For a flat index, `Memory` holds a single node identifier; for a group, it holds sub-memories for each component.

The Rayon worker pool handles the complete feed cycle. Rayon routes nested parallel tasks to the pool of the active thread, so resolvers querying the factory reuse existing workers without spawning extra threads.

## Modeling structures

The kernel includes two specialized graph and algebraic structures designed for `seer`. In `seer`, branching in the syntax graph requires copying state frequently, so these structures are optimized for cheap cloning.

### BooleanPolynomialRing: conflicts

Determining which table provides an unqualified column maps to a boolean function over one variable per table. A column present across `k` tables introduces an "exactly one of `k`" constraint. Selecting multiple columns multiplies these constraints together in a polynomial ring over `GF(2)[t..]/(t^2 - t)`.

`algebra/zdd.rs` implements this using a zero-suppressed decision diagram (ZDD) without external dependencies like CUDD. Nodes are hash-consed to equal `u32` identifiers, with memoization per operation. The multiplication implementation follows PolyBoRi's `dd_multiply`, computing three cross terms using two recursive calls. `algebra/ring.rs` wraps this in a ring interface.

The ZDD representation keeps state compact: while "exactly one of `k`" expands to $2^{k-1}$ monomials over GF(2), the ZDD requires only two nodes per level.

```python
ring = kl.BooleanPolynomialRing(["users", "posts", "comments"])

body = ring.mutual_exclusion(["posts", "comments"])   # `body` is on both
title = ring.mutual_exclusion(["posts"])              # `title` is only on posts

current = ring.product(ring.one(), body)
current = ring.product(current, title)

ring.render(current)         # 'posts & ~comments'
ring.constrained(current)    # frozenset({'posts', 'comments'})
ring.viable(current)         # frozenset({'posts', 'users'})
ring.holds_empty(current)    # False - the FROM clause is not settled yet
```

Polynomial values cross the Python boundary as integer node identifiers, enabling fast copies and comparisons across branches. Batch functions like `nonzero` and `viable` run selection loops entirely in Rust.

### Multigraph: joins

The FROM clause traverses a foreign key graph, opening at an initial table and contracting joined neighbors into a single composite vertex. Because the schema graph is static after initialization, vertex contraction is the only required mutation.

`Multigraph` optimizes for cheap copies across syntax branches. Edges reside in a shared immutable base graph, while mutable state consists of an array tracking vertex mappings.

```
copy              Two reference count bumps, no allocation
merge_vertices    One clone of an array of u32, then a linear pass
edges             The class members' base incidence, mapped through it
```

Branches without joins perform no allocations. Self-loops created by vertex contraction are omitted automatically during edge lookups.

```python
graph = kl.Multigraph([
    ("users", "posts", "posts.user_id = users.id"),
    ("posts", "comments", "comments.post_id = posts.id"),
])

branch = graph.copy()

branch.edges("users")          # [('posts', 'posts.user_id = users.id')]

branch.merge_vertices("users", "posts")

branch.edges("users")          # [('comments', 'comments.post_id = posts.id')]
"posts" in branch              # False - it is part of `users` now
graph.nodes()                  # ['comments', 'posts', 'users'] - untouched
```

Edge labels are opaque strings preserved for caller lookup.

### Python API

The Python bindings fix `N` (node index) and `T` (token ID) types to `u32` and use `FlatDFA` as the default DFA backend. The library can be rebuilt with different configurations by adjusting the types in `pyfactory.rs`, `pyvocabulary.rs`, `pyexpression.rs`, and `pylattice.rs`.

```python
import kernel_typed as kl

# EOS token ID = 1
vocabulary = kl.Vocabulary.from_file_path("vocabulary.tiktoken", 1)

ac_base = kl.AhoCorasick(vocabulary)
lattice = kl.Lattice("hello", vocabulary, ac_base)

toktrie = kl.TokTrie(vocabulary)
expression = kl.Expression("mon|tue|wed", vocabulary, toktrie)
```

Index construction releases the Python GIL, allowing `Lattice`, `Expression`, and the base caches to build concurrently across threads without touching Python interpreter state. `Factory` and `Runner` handle threading internally; `Runner.feed` holds the GIL only when executing the resolver.

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(8) as pool:
    indexes = list(pool.map(lambda p: kl.Expression(p, vocabulary, toktrie), patterns))
```

PyO3 0.22 requires setting `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` when building against Python 3.14.

### Rust API

Requires [Rust](https://rustup.rs).

The Rust dynamic API mirrors the Python interface, using a `Resolver` trait instead of a callback function:

```rust
impl Resolver<Part> for Grammar {
    fn resolve(&self, report: &Report<'_, Part>) -> Expansion<Part> {
        match report.payload {
            Part::Greeting => Expansion::Children(vec![
                Request::new(Draft::Lattice(" ".to_string()), Part::Space),
            ]),
            Part::Space => Expansion::Children(vec![
                Request::existing(self.alias, Part::Alias),
            ]),
            Part::Alias => Expansion::Terminal,
        }
    }
}
```

The head payload is generic, allowing callers to store arbitrary state needed to navigate their own grammar graphs.

See `example.rs` and `runner.rs` for implementation details!

```bash
cargo run --bin example   # Own an index and walk it by hand
cargo run --bin runner    # The factory, the head pool and a group
```

#### Output of running `example`

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