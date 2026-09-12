# kernel

Directed graph generator library for LLM token guidance. Translates regular expressions and constant strings to DFAs, inheriting the AOT data structure of `outlines-core` with further optimizations.

**Lattices** convert constant strings into DAGs using the Aho-Corasick algorithm with extremely fast construction.

**Expressions** convert regular expressions into DFAs using TokTrie with derivative automata.

**Groups** subtract: one inclusion minus any number of exclusions, which is how an alias becomes "any identifier that is not a reserved word".

On top of those it offers a **dynamic API** - a factory that keeps the indexes and answers with ids, and a runner that keeps a pool of active indexes walking them over a pool of workers. The graph being walked stays with the caller: the kernel only says when a head has finished, and asks what comes next.

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

## The dynamic API

Two objects, and one callback.

**`Factory`** is the index registry. It never hands an index back, only an id.
An index is built at most once however many callers ask for it and however many
threads ask at the same moment, so a head is cheap: it borrows a shared index
instead of owning one.

**`Runner`** is the pool of active indexes - *heads*. Each head is a `Memory`
over an index (where the walk stands and what it has consumed) plus an opaque
payload the kernel never looks inside. Feeding a token advances every head
across the workers; the ones that reject it die.

**The resolver** is how the kernel asks what happens next. When a head reaches
the end of its index the runner calls it with `(head_id, payload, matched)` and
takes back either `None` - nothing follows, the generation is complete - or
the `(spec, payload)` pairs of the indexes that do. Those are built on the same
workers and become the next heads, and the loop repeats until nothing new
appears.

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

    return None                      # the end of the graph

runner.set_resolver(resolve)
runner.spawn(("lattice", "hello"), "greeting")

while not runner.is_completed():
    token_id = pick(runner.routes())   # your sampler
    runner.feed(token_id)

print(runner.matched())
```

An index is named either by its id or by the spec to build it from:

```python
("lattice", "SELECT")                        # a constant string
("expression", "[a-zA-Z_][a-zA-Z0-9_]*")     # a regular expression
("group", include_id, [exclude_id, ...])     # include minus the excludes
```

`runner_example.py` is this, runnable.

### Groups

A group accepts exactly when its inclusion accepts and none of its exclusions
do. While an exclusion still spells what has been matched, the group is
*blocked*: it does not report itself finished, and it drops the terminating
token from its routes, so generation has to continue until the identifier grows
past it.

```
hello    the inclusion accepts, but so does an exclusion  -> blocked
hello2   the `hello` exclusion died on the `2`            -> accepted
hell     no exclusion spells it                           -> accepted
```

An exclusion that rejects a token is anchored at the start of the word and can
never match again, so the memory drops it. That is what keeps a wide group cheap:
subtracting 85 names costs a head about as much as the inclusion alone, because
nearly all of them die on the first token.

Either side of a group may itself be a group, so subtractions nest.

### Memory, and where the parallelism goes

Indexes carry no position - a `Lattice` is a table of token edges per byte
offset, an `Expression` is a DFA, and both are immutable once built. The walk
over one is the `Memory`, and there is one per head. For a flat index that is a
single node id; for a group it is one sub-memory per member, which is what makes
groups of groups fall out rather than needing a second mechanism.

The worker pool covers a whole feed rather than just the stages that fan out
inside the runner. Rayon routes nested parallel work to the pool the current
thread belongs to, so a resolver that reaches back into the factory shares these
workers instead of starting a second pool, and a group with enough members fans
its own feed out over them too.

## Setup

### Python API

Requires [Rust](https://rustup.rs) and [UV](https://docs.astral.sh/uv/getting-started/installation).

```bash
make build
source .venv/bin/activate
python example.py                # own an index and walk it by hand
python runner_example.py         # the factory, the head pool and a group
```

The Python bindings fix both `N` (node index) and `T` (token ID) types to `u32` and use `FlatDFA` as the default DFA backend. The library can be rebuilt with different `N` / `T` / `D` configurations, but (at the moment) the source code needs to be modified for it (in the top of `pyfactory.rs` / `pyvocabulary.rs` / `pyexpression.rs` / `pylattice.rs`).

```python
import kernel_typed as kl

# EOS token ID = 1
vocabulary = kl.Vocabulary.from_file_path("vocabulary.tiktoken", 1)

ac_base = kl.AhoCorasick(vocabulary)
lattice = kl.Lattice("hello", vocabulary, ac_base)

toktrie = kl.TokTrie(vocabulary)
expression = kl.Expression("mon|tue|wed", vocabulary, toktrie)
```

See `example.py` for owning indexes directly, and `runner_example.py` for the
factory, the head pool and a group index.

Index construction releases the GIL, so `Lattice`, `Expression` and the two
bases can be built from several Python threads in parallel. The work touches no
Python state while the GIL is dropped. The `Factory` and `Runner` do this for
you - a `Runner.feed` holds the GIL only while calling the resolver - so reach
for a thread pool here only when owning the indexes directly.

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(8) as pool:
    indexes = list(pool.map(lambda p: kl.Expression(p, vocabulary, toktrie), patterns))
```

PyO3 0.22 refuses to build against Python 3.14 unless
`PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` is set; the extension itself works.

### Rust API

Only requires [Rust](https://rustup.rs).

```bash
cargo run --bin example          # own an index and walk it by hand
cargo run --bin runner           # the factory, the head pool and a group
```

The dynamic API is the same shape as it is from Python, with the resolver as a
trait rather than a callable:

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

The head payload is a type parameter, so the kernel carries whatever the caller
needs to find its way back into its own graph and never looks inside it.

See `example.rs` and `runner.rs` for API details!

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
