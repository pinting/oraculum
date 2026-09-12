# seer

An SQL syntax graph generator that constrains an LLM to emit only `SELECT`
statements that are valid *against a specific schema*. The automata work --
building indexes, walking them, and driving them across a worker pool -- lives
in [`kernel`](../kernel); everything here is modelling.

## Architecture

The split runs through `src/engine.py`, and it is worth stating plainly because
it decides where every other question is answered:

* the **kernel** owns the indexes and the *heads* walking them. It never hands
  an index back, only an id; feeding a token advances every head across its
  worker pool; and when a head reaches the end of its index it says so.
* **seer** owns the graph. It answers that notification: it takes the payload
  the head carried -- the `Node` it was spawned from -- applies whatever was
  matched to that node's `Context`, runs its thunk, and replies with the
  indexes that may follow.

Neither side knows the other's subject. The kernel has never heard of SQL, and
nothing here builds a DFA or starts a thread.

```
  src/factory.py     drafts in, kernel index ids out
  src/engine.py      the syntax graph, and the kernel's resolver
  src/graph.py       the SQL SELECT language
  src/context.py     the generation state a node is resolved against
  src/debug.py       the state tracing described below

  main.py            interactive driver
  live.py            model driven driver (llama.cpp)
  core.py            the vocabulary and engine both drivers share
```

The modelling under `Context` comes from `experiments/9-advanced-modelling`:

```
experiments/9-advanced-modelling/
  schema.py                        src/schema.py
  root.py                          src/root.py
  scope.py                         src/scope.py
  scopes.py                        src/scopes.py
  conflicts.py                     src/conflicts.py
  relationships.py                 src/relationships.py
  main.py          (TUI)           -- folded into src/graph.py, see below
```

### What the modelling is made of

`Context` answers two kinds of question, and they correspond to the two phases
of a `SELECT`:

| Module             | What it does                                   |
| ------------------ | ---------------------------------------------- |
| `root.py`          | the unqualified table space, as a GF(2) ring   |
| `scope.py`         | one alias, and the table it can still be       |
| `scopes.py`        | aliases as first class `"table alias"` nodes   |
| `conflicts.py`     | one facade over both                           |
| `relationships.py` | the foreign key join graph                     |
| `schema.py`        | sqlglot, with types and foreign keys           |

**`root.py`** models the unqualified table space as a Boolean polynomial ring
`GF(2)[t1, ..., tn]`. A field living in tables `{t1..tk}` contributes the mutual
exclusion polynomial

```
C(f) = SUM_i  t_i * PRODUCT_(j != i) (1 + t_j)
```

and a running product `P <- P * C(f)` accumulates the selection. `P = 0` means
the selection is contradictory; substituting `t = 1` asks whether a table is
viable; evaluating with every variable at zero asks whether the query is
settled.

**`relationships.py`** is the piece with no Rust ancestor at all. Foreign keys
become a multigraph over table names, joining merges the neighbour into the
head, and the head's neighbourhood becomes the union of both -- which is exactly
SQL's rule that a join makes all columns of both tables reachable.

### SageMath

`root.py` and `relationships.py` use the same SageMath structures the
experiment does -- `BooleanPolynomialRing` for the GF(2) ring and `Graph` for
the foreign key multigraph -- rather than reimplementing them.

SageMath only installs system-wide, so the virtualenv has to be created with
access to the system packages. `make build` does this and refuses to go on if
it cannot find a Python that imports `sage`:

```bash
sudo pacman -S sagemath          # or your distribution's equivalent
make build                       # creates .venv --system-site-packages
```

An existing `.venv` built without `--system-site-packages` is detected and
reported rather than half-working; `make distclean build` recreates it.

It earns its place on speed as well as on fidelity. PolyBoRi, the C++ engine
behind Sage's boolean polynomials, resolves a cold 2401 field expansion in
57 ms where a pure-Python BDD of the same semantics needed 96 ms. The ring
itself costs ~9 ms to build for a three table schema, a multiply is ~0.2 us and
a substitution ~1.2 us, and `import sage.all` adds ~0.7 s to start-up.

Cloning stays cheap: the ring, its variables and the constraint polynomials
never change after construction, so `Root.copy()` shares them and polynomials
are values, so `current` needs no copying at all. Sage's polynomial operations
are also safe to use from the kernel's workers -- `tests/test_threading.py`
hammers a shared ring from eight of them and checks the results still match a
single-threaded run.

`tests/test_experiment_parity.py` drives this port and the experiment's
original over the same cases and compares their traces step for step, which is
what pins the adaptations below to the behaviour they came from.

### The two phases, on a token stream

The experiment's TUI runs two menu loops with a hard boundary: select fields
until `[Done]`, then pick tables and join them. seer has the same boundary, but
it falls on a token -- the `FROM` keyword, whose selector calls
`Context.enter_from()`. That is where the join graph is built, because only then
is the required table set final.

```
                    fields                    FROM                 tables
    Conflicts ------------------> required -----------> Relationships -----> satisfied
      Root (unqualified)                                  join graph
      Scopes (aliases)
```

### Adapting the experiment's IO

The experiment was written for a menu, and three of its habits do not survive
contact with a token driven engine:

* **Exceptions become booleans.** A TUI catches the error and re-prompts; seer
  applies selections speculatively while expanding nodes, so `use_field` and
  `use_table` report failure with a bool and leave the resolver untouched.
* **Sets become sorted sequences.** Set iteration order is not stable, and the
  syntax graph has to expand the same way on every run.
* **Nothing was ever cloned.** Every branch of the graph needs its own state, so
  each entity grows a `copy()` that shares the parts that are immutable once
  built -- the BDD store, the constraint table, the field index.

One bug does not carry over either: the experiment registers a scope *before*
narrowing it, so an alias whose first field is rejected is left behind as an
empty scope that requires every table. Here the scope is only registered once
its first field applies.

Column references also had to change. The experiment formats them as
`"comments c.user_id"`, which reads fine in a menu but is not valid SQL, and
seer emits these tokens verbatim -- so an aliased node is referenced by its
alias (`c.user_id`) and written as `comments AS c`.

## The language

`src/graph.py` describes the grammar as `Thunk`s rather than as a structure. A
thunk is only given a `Context` when generation reaches it, which is what lets
the alternatives depend on what has already been selected.

```
SELECT <fields> FROM <entry> [, <entry>]* ;
  <entry>     := <table> [AS <alias>] [<join>]*
  <join>      := <join type> <table> [AS <alias>] ON <column> = <column>
  <fields>    := <field ref> [, <field ref>]*
  <field ref> := <field> | <alias>.<field>
```

The experiment's outer FROM loop is `from_entry` plus `finish`, its inner JOIN
loop is `joins`, and its JOIN TYPE menu is a branch over the four join types.

Feeding a token advances every live head. A head that reaches an accepting
state is reported to `Engine.resolve`: its selector records what was matched
into a fresh `Context`, its thunk produces child `Node`s, and each child is
spawned as a head of its own. This repeats to a fixpoint.

What the modelling buys is that the alternatives are always both grammatical and
semantically legal:

```
SELECT email, title FROM users INNER JOIN posts ON users.id = posts.user_id;   accepted
SELECT email, title FROM users INNER JOIN posts ON users.id = posts.id;        rejected -- not a foreign key pair
SELECT email FROM users INNER JOIN users ON users.id = users.id;               rejected -- no foreign key path
SELECT post_id FROM users;                                                     rejected -- post_id needs comments
SELECT email FROM posts;                                                       rejected -- no selected field needs posts
SELECT c.first_name FROM comments AS c;                                        rejected -- the alias has no first_name
SELECT title FROM posts, comments;                                             rejected -- title resolves to exactly one table
```

The `ON` columns are not guessed: once the join target is chosen they are the
only tokens on offer, because the foreign key determines them.

### Aliases

An alias is the one piece of a statement the schema says nothing about -- it is
invented by whoever is generating -- so the only shape available for it is the
identifier pattern. That pattern is too wide on its own. `users` matches it, and
so does `SELECT`, which would make `SELECT users.email` open a namespace named
after a table and `SELECT SELECT.x` legal.

`graph.alias` therefore matches a **group index**: the identifier pattern minus
one lattice per reserved word, table name and field name.

```python
IndexDraft.group(
    IndexDraft.expression(IDENTIFIER),
    [IndexDraft.lattice(name) for name in ctx.get_reserved_names()],
)
```

A group accepts exactly when its inclusion accepts and none of its exclusions
do. While an exclusion still spells what has been matched the group is *blocked*
-- it does not report itself finished, and it stops offering the terminating
token -- so generation has to continue until the identifier grows past it:

```
u        accepted
users    blocked  -- a table
users2   accepted -- the `users` exclusion died on the `2`
email    blocked  -- a field
SELECT   blocked  -- reserved
```

`Context.get_reserved_names()` is the subtracted set: the SQL keywords of
`schema.RESERVED` in both cases, plus every table and column name. It is
constant for a schema, so it is computed once and carried by `copy()`.

This also closes a wart. `Scopes` treats any namespace as an alias that the
FROM clause must satisfy as `table AS alias`, so `SELECT users.email FROM users`
never had a way to complete -- it required `FROM users AS users`. The
subtraction makes that unreachable rather than merely unsatisfiable.

## Debug tracing

The experiment's TUI reprints the whole resolver state after every menu choice,
which is what makes its two loops readable. seer has no menu, so the equivalent
is to print the same block after every operation that modifies a `Context`:
`set_current_namespace`, `use_field`, `enter_from`, `use_table` and
`join_table`. Queries never trace.

`Context.__str__` is that block -- the six lines of `Conflicts.__str__` plus the
`Used references` line the experiment's `Relationships.__str__` appended once
phase two began. The lines underneath come from the same `__str__` methods as
in the experiment: `Root` simplifies its polynomial to DNF through `sympy`,
`Scope` joins its candidates with `^`, and `Scopes` lists each alias.

Both drivers trace by default; pass `--no-debug` to silence them.

```
── use_field(p.title) ──────────────────────────────────────────
Satisfied        = False
Selected fields  = u.email, p.title
Excluded fields  = 
Root tables      = True
Scopes tables    = p = posts; u = users
Excluded tables  = comments p, comments u, posts u, users p
Used references  = 

── use_table(users u) ──────────────────────────────────────────
Satisfied        = False
Selected fields  = u.email, p.title
Excluded fields  = 
Root tables      = True
Scopes tables    = p = posts; u = 1
Excluded tables  = comments p, comments u, posts u, users p, users u
Used references  = users AS u

── join_table(INNER JOIN posts AS p ON u.id = p.user_id) ───────
Satisfied        = True
...
```

Leaving it on is cheap. Selectors only run when a head reaches an accepting
state, not on every speculative expansion, so a whole statement produces eight
blocks rather than one per branch explored. Rendering is lazy too, since
`Root.__str__` runs a sympy simplification that should not happen while tracing
is off.

One thing the trace makes visible is that the engine explores readings in
parallel: feeding `email` can produce both a `set_current_namespace(email)` and
a `use_field(email)` block, because until the next token arrives the graph
cannot know whether `email` is a field or an alias awaiting a `.`.

## Entry points

Both drivers build their engine through `core.init_engine` and both take
`--threads`, which is the size of the kernel's worker pool.

| File      | Mode         |
| --------- | ------------ |
| `main.py` | interactive  |
| `live.py` | model driven |

```bash
python main.py --threads 8      # walk the graph by hand
python live.py --threads 8      # let a llama.cpp model walk it
```

## The kernel boundary

`Engine` holds a `kernel.Runner` and registers `Engine.resolve` as its
resolver. After that, one `feed` looks like this:

```
   engine.feed(token)
     |
     +-- kernel: advance every head over the token, across the workers
     |           heads that reject it die
     |
     +-- kernel: for each head that reached the end of its index
     |     |
     |     +-- seer: Engine.resolve(head_id, node, matched)
     |           selector -> a fresh Context
     |           thunk    -> child Nodes
     |           factory  -> the kernel spec each child wants
     |
     +-- kernel: build those indexes, across the workers
     |           spawn a head per index
     |
     `-- repeat until nothing new appears
```

The number of workers changes nothing an observer can see -- same heads, same
routes, same accepted language, same number of index builds --  and
`tests/test_threading.py` asserts that step by step at 1, 2 and 8 workers.

Three things keep the fan-out from costing more than it saves:

* **The pool covers the whole feed.** Rayon routes nested parallel work to the
  pool the current thread belongs to, so a resolver that reaches back into the
  factory -- which is what building a wide group draft does -- shares these
  workers instead of starting a second pool of its own.
* **A memoising registry.** Indexes are immutable and carry no position, so one
  index backs every head that asks for it. The position lives in the kernel's
  `Memory`, one per head.
* **Single flight.** Several workers asking for the same unbuilt draft share
  one build rather than each paying for it.

`kernel` releases the GIL for the duration of a feed, and takes it back only to
call the resolver. Index construction touches no Python state, so a batch of
builds runs with the interpreter free.

## Results

Measured with `python benchmark.py --runs 5` on a GIL-enabled CPython 3.14 with
the 255 386 token Gemma 3 vocabulary.

Raw index construction, 16 distinct expressions -- the ceiling for everything
downstream:

| threads | time (ms) | speedup |
| ------- | --------- | ------- |
| 1       | 509.3     | 1.00x   |
| 2       | 272.5     | 1.87x   |
| 4       | 145.4     | 3.50x   |
| 8       | 80.3      | 6.34x   |

Cold expansion of `SELECT `, where every field in the schema becomes a head, as
the schema widens (ms). Engine construction is excluded: it builds the GF(2)
ring, which for the widest case costs more than everything measured here put
together and has nothing to do with the head pool.

| schema | fields | 1 thr | 2 thr | 4 thr | 8 thr | speedup |
| ------ | ------ | ----- | ----- | ----- | ----- | ------- |
| 5x5    | 30     | 14.6  | 14.7  | 15.2  | 14.7  | 1.00x   |
| 15x15  | 240    | 15.2  | 15.6  | 15.1  | 15.0  | 1.01x   |
| 30x25  | 780    | 17.5  | 17.0  | 17.0  | 17.2  | 1.03x   |
| 60x40  | 2460   | 25.0  | 22.7  | 22.9  | 22.9  | 1.10x   |

The engine-level gain is nowhere near the 6.3x the same hardware reaches on
index building, and the reason is the workload rather than the pool. Profiling
a cold 60x40 expansion puts ~18 ms of its ~25 ms inside one index build: the
identifier pattern `[a-zA-Z_][a-zA-Z0-9_]*`, which takes that long to compile
against this vocabulary. It is a *single* build, so no number of workers
shortens it, and it sits on the critical path of every cold expansion because
the alias group includes it.

What is left over does parallelise. Building all 2460 field lattices in
isolation:

| workers | time (ms) |
| ------- | --------- |
| 1       | 4.3       |
| 2       | 2.8       |
| 4       | 2.1       |
| 8       | 2.5       |

It flattens at 4 because a lattice takes under 2 us to build, which is close
enough to the dispatch cost that more workers stop helping.

Warm per-token latency is unaffected by the pool, as it should be -- below the
dispatch threshold the workers are skipped entirely:

| workers | median   | max      |
| ------- | -------- | -------- |
| 1       | 0.071 ms | 0.240 ms |
| 4       | 0.066 ms | 0.241 ms |

### What a group costs

The alias group for the three table schema subtracts 85 names -- 74 SQL
keywords in both cases, 3 tables and 8 fields. A head on it therefore carries
86 memories rather than one.

| index               | spawn + one token |
| ------------------- | ----------------- |
| the identifier only | 0.045 ms          |
| the group           | 0.046 ms          |

It is close to free because of two things. The exclusions are lattices, so one
step is a handful of comparisons; and a memory *prunes* itself -- an exclusion
that rejects a token is anchored at the start of the word and can never match
again, so it is dropped. Nearly all of the 85 die on the first token, leaving a
handful to walk for the rest of the head's life.

## Setup

Requires [Rust](https://rustup.rs), [UV](https://docs.astral.sh/uv/getting-started/installation),
Python 3.14 and **SageMath installed system-wide**, since it cannot be
installed into a virtualenv:

```bash
sudo pacman -S sagemath          # or your distribution's equivalent
```

`make build` then creates `.venv` with `--system-site-packages` so it can see
Sage, builds `kernel` against that interpreter and installs the wheel into
it. It stops with a clear message if no Python 3.14 with Sage is found, or if
an existing `.venv` was created without access to the system packages.

```bash
make build       # venv + kernel + runtime dependencies
make test        # 240 tests
make benchmark
make run         # main.py, interactive
make live        # live.py, model driven
make distclean   # also removes .venv, to recreate it
```

### Interactive mode -- `main.py`

Needs only the vocabulary file. One vocabulary token per line, so a word may
take several turns.

```bash
source .venv/bin/activate
python main.py                 # one kernel worker
python main.py --threads 8     # eight
python main.py --schema my.sql
python main.py --no-debug      # without the state blocks
```

Picking up after `SELECT email, title FROM users` (routes elided with `...`):

```
Routes: ` `, ` ,`, `,`, `F`, `FU`, `FUL`, `FULL`, `I`, `IN`, `INN`, `INNER`, `L`, `LE`, `LEFT`, `R`, ...
> INNER
Matched: `SELECT email, title FROM users INNER`
Routes: ` `, ` J`, ` JO`, ` JOIN`
>  JOIN
Routes: `c`, `co`, `com`, `comm`, `comme`, `comment`, `comments`, `p`, `po`, `pos`, `post`, `posts`, ...
> posts
Routes: ` `, `O`, `ON`, ...
> ON
Routes: `u`, `us`, `use`, `user`, `users`, ...
> users
Routes: `.`
> .
Routes: `i`, `id`
> id
...
Matched: `SELECT email, title FROM users INNER JOIN posts ON users.id = `
Routes: `p`, `po`, `pos`, `post`, `posts`, ...
> posts
Routes: `.`
> .
Routes: `u`, `us`, `use`, `user`
> user
Routes: `_`
> _
Routes: `i`, `id`
> id
Matched: `SELECT email, title FROM users INNER JOIN posts ON users.id = posts.user_id`
Routes: ` `, `;`, ...
> ;
Matched: `SELECT email, title FROM users INNER JOIN posts ON users.id = posts.user_id;`
```

Only the four join types are offered after a table, only tables with a foreign
key path after `JOIN`, and once the target is chosen the `ON` columns are
forced -- after `users.` the single route is `id`, and after `= posts.` it is
`user_id`.

### Model driven mode -- `live.py`

Additionally requires `llama-cpp-python` and the
[gemma-3-4b-it-Q8_0](https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF)
model at `../models/`.

It serialises the model's vocabulary, **overwriting `../vocabulary.tiktoken`**,
builds the engine over it and masks the logits at every step, so the model can
only sample tokens the syntax graph allows.

```bash
make model                     # adds llama-cpp-python
python live.py --threads 8
python live.py --no-debug      # without the state blocks
python live.py --model ../models/other.gguf --prompt "List every post title!"
```

```
Loading model from ../models/gemma-3-4b-it-Q8_0.gguf...
Model loaded successfully!
Resolving nodes on 8 threads (GIL enabled)
Loaded 255385 tokens
Vocabulary saved successfully!
Generating response...

12874 b'SELECT'   107 b'\n'    140 b'    '   236756 b'u'      236761 b'.'
6774 b'email'    236764 b','   107 b'\n'    140 b'    '      236758 b'p'
236761 b'.'      3250 b'title' 107 b'\n'    28337 b'FROM'    ...
167459 b'INNER'  34653 b' JOIN'               22487 b'posts'  ...
236756 b'u'      236761 b'.'   547 b'id'     236784 b'='      236758 b'p'
236761 b'.'      2364 b'user'  236779 b'_'   547 b'id'        236793 b';'

Matched: `SELECT
    u.email,
    p.title
FROM
    users
    AS  u
    INNER JOIN
    posts
    AS  p
ON
    u.id  =  p.user_id;`
```

Prompted for "the email of every user together with the titles of their posts",
the model reached for two aliases, and every part of the modelling had to agree:
`u` and `p` are `Scope`s narrowed to users and posts, the join is the foreign
key `posts.user_id -> users.id` found in the graph, and the `ON` columns were
the only tokens on offer by the time it got there. It picks its own layout --
the `[ \n\t]+` separators accept the newlines and indentation -- and stops at
the `;`.

## Notes

`Engine.feed` drops every head when a token is rejected, as a plain DFA walk
would, which leaves the engine with no routes.

Where seer deliberately differs from the experiment it takes its modelling
from:

* **Resolvers report failure with a bool** instead of raising, and their queries
  return sorted sequences instead of sets. See *Adapting the experiment's IO*.
* **An alias is only registered once its first field applies.** The experiment
  registers the scope first, so a rejected first field leaves an empty scope
  that requires every table.
* **`ON` columns are written as SQL.** The experiment renders them
  `"comments c.user_id"`; seer emits `c.user_id` and `comments AS c`.
* **An alias cannot spell a reserved word, table or field.** See *Aliases*;
  the experiment's menu had no way to type an ambiguous one in the first place.
* **`live.py` stops once the statement is complete**, rather than relying on
  the route set emptying out, which would leave the model sampling past the `;`.
* **`core.init_vocabulary` rejects an empty vocabulary.** `kernel` accepts
  malformed input and yields zero tokens rather than failing, which would
  otherwise build an engine with no routes and no error.

Everything the experiment printed is ported, including the `sympy` DNF
rendering in `Root.__str__`. What is new is *when* it prints: after each
modifying `Context` operation rather than after each menu choice.

## License

This project is licensed under the [GNU Affero General Public License v3.0](../LICENSE).
