# oraculum

An SQL autocomplete framework which guarantees grammatical and semantical correctness in the following subset of the language.

```xml
<statement> := SELECT <fields> FROM <entry> [, <entry>]* [WHERE <filters>] ;

<fields>    := <field ref> [, <field ref>]*
<field ref> := <field> | <alias>.<field>

<entry>     := <source> [<join>]*
<join>      := <join type> <source> ON <column ref> = <column ref>
<source>    := <table> [AS <alias>]
<join type> := INNER JOIN | LEFT JOIN | RIGHT JOIN | FULL JOIN

<filters>   := <predicate> [(AND | OR) <predicate>]*
<predicate> := [NOT] (<condition> | "(" <filters> ")")
<condition> := <operand> <operator> <operand | literal>
             | <operand> IS [NOT] NULL
<operand>   := <column> | <qualifier>.<column>
```

## Setup

Needs [Rust](https://rustup.rs), [UV](https://docs.astral.sh/uv/getting-started/installation)
and Python 3.14. Everything else is downloaded at a version this repository
names.

Each project builds itself, from its own directory:

```bash
cd seer
make build       # seer and the kernel, natively
make test        # the corpus, one character at a time
make run         # interactive: the graph offers tokens, you pick one
make live        # the same, with a model doing the picking
make wasm        # the same kernel, cross compiled to WebAssembly
```

```bash
cd kernel
make build       # the kernel alone, into its own venv
make benchmark   # DFA layouts, timed
```

```bash
make docs        # the browser build, into docs/
```

## Acknowledgement

The foundational experiments, designing the architectural layers of grammatical and semantic rulesets, were carried out with the blood and sweat of old-fashioned human work. For the later stages, Anthropic's `Claude Opus 4.6 - 5.5` and Google's `Gemini 3.1 Pro` large language models were heavily used to port code between Python and Rust, introduce new targets and extend the supported subset of SQL. While these models are excellent tools, caution is mandatory, as they can get entangled over time if their generated spaghetti code is not tamed.

## Introduction

Imagine a text box where you type SQL and the system only ever offers you tokens that lead to a valid, answerable query. You write `SELECT em` and it completes `email` but not `body` if the table you are heading towards does not have a `body`. You have not typed `FROM` yet but the system already knows which tables are still possible. When you do get to `FROM`, only the tables that can actually answer your projection show up, the `ON` clause of a join writes itself from the foreign keys and the `WHERE` clause only offers operators that make sense for the column's type. Every token the model produces is guaranteed correct, grammatically and semantically, without any post validation.

### WASM based demo

<p align="center">
  <a href="https://pinting.github.io/oraculum/">
    <img src="preview.png" max-width="1150">
    Click here the open the demo.
  </a>
</p>

### Atoms

**Token trees:** A language model writes in tokens, fixed pieces drawn from a vocabulary of hundreds of thousands of entries, each covering one or more characters. The same keyword can arrive as one piece or many and every way of spelling it forms a path through a graph over the character positions in the string:

```mermaid
graph LR
    p0((0)) -->|"F"| p1((1))
    p1 -->|"R"| p2((2))
    p2 -->|"O"| p3((3))
    p3 -->|"M"| p4((4))

    p0 -->|"FR"| p2
    p0 -->|"FROM"| p4
    p1 -->|"ROM"| p4
    p2 -->|"OM"| p4

    classDef plain fill:#4a5160,stroke:#2f343f,color:#ffffff
    classDef accent fill:#2f6fb5,stroke:#1b4670,color:#ffffff
    class p0,p1,p2,p3 plain
    class p4 accent
```

Each edge is a vocabulary token whose text covers exactly those positions. A path from 0 to 4 is one valid tokenisation of `FROM`. To enforce grammar at the token level every grammatical element (a keyword, an identifier pattern, a literal format) has to become an automaton that accepts exactly the token sequences spelling it.

**Constants and patterns as automata:** A fixed keyword like `FROM` is the position graph above, already a DFA over tokens: acyclic, one accepting state, found by a single Aho-Corasick sweep of the vocabulary. A regular expression cannot be drawn as positions. Instead the states are the **derivatives** of the regex: strip one character and see what regex is left. The identifier pattern `[a-z_][a-z0-9_]*` has exactly two live states:

```mermaid
graph LR
    s0(["[a-z_][a-z0-9_]*"]) -->|"letter / underscore"| s1(["[a-z0-9_]*"])
    s1 -->|"letter / digit / underscore"| s1

    classDef plain fill:#4a5160,stroke:#2f343f,color:#ffffff
    classDef accent fill:#2f6fb5,stroke:#1b4670,color:#ffffff
    class s0 plain
    class s1 accent
```

The first character class is consumed and the starred tail loops on itself. Two derivatives, two states. Transitions on vocabulary tokens walk all characters at once, pruned by a trie so that dead prefixes skip whole subtrees.

**The grammar as an NFA:** Wire the keyword constants and identifier patterns as edges in a graph whose shape is the SQL grammar. Every edge label is one of the automata from the previous step: a constant, a pattern or a difference of patterns. Walking an edge means feeding tokens into that automaton until it accepts, then following the grammar arc. Multiple edges out of one node are multiple live branches, which makes the graph an NFA. The system determinises lazily, one token at a time, rather than building the exponential product machine up front.

**Latent state, enabling and disabling routes:** The grammar graph is static: it knows that *a* field follows `SELECT` and *a* table follows `FROM`, but not which ones. A second layer, the latent state, rides alongside the walk and enables or disables edges as the query grows.

The latent state holds what the query has committed to so far. Each branch of the walk has its own copy, so one branch never sees the choices of another. An edge is offered only if the query can still be completed after taking it.

What the state tracks depends on the clause. In the projection it works out which tables could still supply the fields selected so far and withdraws any field that would contradict the selection. In the FROM clause it offers only the tables the projection needs and a join only reaches a table linked to the entry by a foreign key, which also fills in the `ON` clause. Once the FROM clause is finished its columns form a fixed table and the rest of the query is written against it: a condition may name only those columns and the type of a column decides which operators and literals can follow it. The terminator is not offered until the FROM clause supplies every table the projection needs. Section 6 covers how each of these is computed.

### An example

With that machinery in place, here is how a concrete query unfolds over a real schema.

```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    verified BOOLEAN,
    created_at TIMESTAMP
);

CREATE TABLE posts (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    published_at TIMESTAMP
);

CREATE TABLE comments (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    post_id BIGINT NOT NULL REFERENCES posts(id),
    body TEXT NOT NULL
);
```

**The projection:** One or more columns, each written root or scoped by an
alias. An alias is invented by whoever is generating, since nothing in the
schema names it, so it may be any identifier that no keyword, table or column
already spells: `users2` is available, `users` is taken. Aliases are
introduced here and nowhere else: `FROM users AS u` is reachable only once
something has written `u.` in the projection.

```sql
SELECT email, first_name FROM users;
SELECT u.email, u.first_name FROM users AS u;
```

What may be written is what the schema can still answer. `email` is on `users`
alone, so writing it settles which table the clause needs. `body` is on `posts`
and `comments`, so it leaves both open until something else decides between
them. A name drops out once nothing that could supply it is left: after
`SELECT id, title` the root `id` has to come from exactly one source and
`title` has pinned that source to `posts`, so `users` is out and `first_name`
is no longer offered. Section 6.1 is how that is computed.

**The FROM clause:** One or more entries, comma separated, each a table
optionally renamed by `AS`. Only tables the projection actually requires are
ever offered and the statement cannot reach its terminator until every one of
them has been supplied.

```sql
SELECT email, body FROM users, comments;
```

**Joins:** Any entry may be grown by any number of joins, in all four types.
The target has to be a foreign key neighbour of the entry as it now stands and
that settles the `ON` columns outright, since they are read off the foreign
key.

```sql
SELECT email, title FROM users INNER JOIN posts ON users.id = posts.user_id;
SELECT email, title FROM users FULL JOIN posts ON users.id = posts.user_id;
SELECT title, c.body FROM posts LEFT JOIN comments AS c ON posts.id = c.post_id;
```

Joining merges the two, so a table two foreign keys away becomes reachable once
the table between them is in. The second join here is only offered because the
first one brought `posts` into the entry:

```sql
SELECT email, title, c.body
FROM users
INNER JOIN posts ON users.id = posts.user_id
INNER JOIN comments AS c ON posts.id = c.post_id;
```

A renamed source answers to its alias everywhere afterwards and to nothing
else, so `FROM users AS u` makes the join `ON u.id = posts.user_id`, never
`ON users.id`. Section 6.3 is the graph this walks.

**The WHERE clause:** Optional and written against the relation the FROM
clause produced: every column of every source it placed, joined or not.
Each is reachable scoped by its source's alias or table name and root
wherever exactly one source supplies the name. A column does not have to be
projected to be filtered on.

```sql
SELECT email FROM users WHERE created_at IS NOT NULL;
SELECT email FROM users WHERE first_name LIKE 'A%';

SELECT email, title
FROM users
INNER JOIN posts ON users.id = posts.user_id
WHERE created_at < published_at;
```

A column's type fixes which operators it may take and what may stand on the
other side of them, which is what makes `created_at < published_at` a statement
about two timestamps and `email = users.id` no statement at all. Sections 6.4
and 6.5 are the relation and this gating.

Conditions combine with `AND` and `OR`, take a `NOT` in front and nest three
brackets deep:

```sql
SELECT email FROM users WHERE email = 'a' AND users.id > 1;
SELECT email FROM users WHERE NOT email LIKE 'a%';
SELECT email FROM users WHERE (email = 'a' OR email = 'b') AND NOT users.id = 1;
```

Two things have to be true of every statement the system produces. It has to be **grammatical**: a well-formed word or phrase. It also has to be **meaningful**: something the system can actually understand. Both are enforced one token at a time while the model is writing, so neither is ever checked after the fact.

## Architecture

### 1. Tokens: characters, words, pieces of text

A grammar talks about text: the word `tiger`, a comma, an identifier. A language model emits **tokens** drawn from a fixed vocabulary and the same text can arrive many ways.

```mermaid
graph LR
    n0((0)) -->|"t"| n1((1))
    n1 -->|"i"| n2((2))
    n2 -->|"g"| n3((3))
    n3 -->|"e"| n4((4))
    n4 -->|"r"| n5((5))

    n0 -->|"ti"| n2
    n0 -->|"tig"| n3
    n0 -->|"tige"| n4
    n0 -->|"tiger"| n5

    n1 -->|"ig"| n3
    n1 -->|"ige"| n4
    n1 -->|"iger"| n5

    n2 -->|"ge"| n4
    n2 -->|"ger"| n5

    n3 -->|"er"| n5

    classDef plain fill:#4a5160,stroke:#2f343f,color:#ffffff
    classDef accent fill:#2f6fb5,stroke:#1b4670,color:#ffffff
    class n0,n1,n2,n3,n4 plain
    class n5 accent
```

To compare the two you have to turn a token sequence back into text, which just means gluing the pieces together. Call that $c$:

```math
c(v_1 v_2 \cdots v_k) \;=\; v_1 v_2 \cdots v_k
```

Gluing carries concatenation of tokens to concatenation of text, $c(xy) = c(x)\,c(y)$, which is the only sense in which the vocabulary is a homomorphism.

So what has to be enforced is the set of token sequences that glue into the set $L$ of legal texts:

```math
c^{-1}(L) \;=\; \{\, w \in V^{*} \;:\; c(w) \in L \,\}
```

That is every way of spelling something in $L$ with this vocabulary. For $L = \{\texttt{"tiger"}\}$ that is the handful of chops above; for an infinite $L$ it is infinite.

$c$ is many-to-one, so $c^{-1}(L)$ is the wider of the two. For an infinite $L$ there is nothing to list at all, so it has to be a machine. Regular languages survive inverse homomorphism, so whenever $L$ is regular that machine is a finite automaton over $V$. It is what `kernel` calls an **index** and sections 2 to 4 are three ways of building one.

```
NOTE: What an index is from outside

You hand the factory a description (a constant, a pattern, or a
difference of other indexes) and get back an id. After that the only
thing anyone says is "advance index 7 by token 1204" and which of the
three kinds it happens to be stops mattering.

The one place it does matter is that a group is built over other indexes
rather than over flat ones, so an exclusion can itself be a difference
and subtractions nest. And none of the three stores a position, which is
why one automaton can sit behind every active index using it.
```

### 2. Constants: a graph over the gaps in a string

Take the constant `tiger`. Put a node at every position in it: before the `t`, between each pair of letters, after the `r`. Six nodes for five characters, because `tiger` is ASCII: positions are byte offsets, so a multi-byte character spans several nodes rather than one. Then draw an edge from $i$ to $j$ whenever some vocabulary token spells exactly the characters between them.

A **path from 0 to 5 is one way of spelling `tiger`** and every way appears as a path. So this graph *is* $c^{-1}(\{\texttt{tiger}\})$, drawn out. It is acyclic because every edge moves right and it has one accepting node, the last one.

The encoding follows from the picture. Group the edges by their source node and two facts let most of the data disappear:

- the label already determines the target, since $j = i + |v|$ with $|v|$ the token's length in bytes, so no target needs storing;
- node $i$ is accepting exactly when $i$ is the last node, so the position *is* the accepting flag and none needs storing either.

The second one turns on reaching the end of the constant, which is a stronger condition than having no outgoing edges: a byte offset in the middle of a multi-byte character has none either and it must not accept.

What is left is the out-edge labels, grouped by source, which is two arrays. Finding the edges in the first place is one **Aho-Corasick** pass: a single automaton holding all 255,386 tokens as patterns, built once per vocabulary, which reports every token occurring anywhere in `tiger` in one sweep. A standalone Go implementation example of this can be found in [`experiments/1-aot-ahocorasick/ahocorasick.go`](experiments/1-aot-ahocorasick/ahocorasick.go).

```
NOTE: What a lattice answers

Ask it which tokens leave position i and it hands back a slice of an
array it already holds, with no allocation and no search. That is the only
question it needs to answer: the target is i plus the token's length in
bytes and reaching the end of the constant is what accepting means, so
neither is stored.

The Aho-Corasick automaton that found the edges is not part of it. It is
built once per vocabulary, read while the arrays are filled and shared by
every lattice afterwards.
```

### 3. Regular expressions: a state is the regex that is left

A constant has a graph you can draw. A regular expression's automaton has to be discovered instead and the trick is to let **the states be regular expressions themselves**.

The *derivative* of a regex $r$ by a character $b$, written $\partial_b r$, is exactly what remains of the regex after stripping off just the **first, single character** $b$:

```math
\partial_b r \;=\; \{\, w \;:\; bw \in L(r) \,\}
```

Counted up to similarity, which treats union as associative, commutative and idempotent, a regular expression has only finitely many distinct derivatives. So the derivatives close into the state set of a finite automaton.

Take the identifier pattern `[a-zA-Z_][a-zA-Z0-9_]*`. Reading a `t` consumes the first character class and leaves the starred tail. Reading another letter from the starred tail leaves the exact same starred tail again:

```
  r          = [a-zA-Z_][a-zA-Z0-9_]*
  d_t(r)     = [a-zA-Z0-9_]*
  d_i(d_t(r))= [a-zA-Z0-9_]* -> The same regex, no new state
```

Two live derivatives means exactly **two states**, which is what the built automaton reports. There is a third, $\emptyset$, reached by starting with a digit; it is the dead state and nothing stores it. Brzozowski's theorem guarantees the search terminates: up to similarity the derivatives are finite in number, so the states run out. `derivre` computes them lazily, materialising a state the first time it is reached. A standalone Go implementation example of this derivation process can be found in [`experiments/2-jit-derivre/brzozowski.go`](experiments/2-jit-derivre/brzozowski.go).

That gives an automaton over *characters*. One more step turns it into one over tokens: to take a token $v$, walk all of its characters at once.

```math
\delta(q, v) \;=\; \partial_{v}\,q \quad\text{- read every character of } v \text{ in turn}
```

Done naively that is 255,386 walks per state. Instead the vocabulary is held as a **trie** and the walk descends it once: the moment a character kills the branch, every token below that prefix is dead too and the whole subtree is skipped.

The automata that come out are tiny in states and enormous in edges:

```
[a-zA-Z_][a-zA-Z0-9_]*     2 states      53,097 and 53,118 edges      849,816 bytes
[ \n\t]+                   2 states                                     1,628 bytes
```

**An index costs its edge count.**

### 4. Difference without a product

A name is any identifier the language and the schema have not already claimed: no reserved word, no table name, no column name. That is a set difference:

```math
L(G) \;=\; L(\mathrm{inc}) \;\setminus\; \bigl( L(\mathrm{exc}_1) \cup \cdots \cup L(\mathrm{exc}_k) \bigr)
```

Regular languages are closed under difference, so an automaton for this exists: the product of the inclusion with the complement of each exclusion. Its states are bounded by the product of theirs:

```math
|Q_G| \;\le\; |Q_{\mathrm{inc}}| \times |Q_{\mathrm{exc}_1}| \times \cdots \times |Q_{\mathrm{exc}_k}|
```

For the example schema above $k$ is 88, growing with the schema, so that product is never built. Instead the members stay separate automata, all of them are fed the same token and the difference is taken **when the word is asked whether it may end** rather than in the state space:

```math
\begin{aligned}
\delta_G(q, v) &= \delta_{\mathrm{inc}}(q, v) && \text{the inclusion alone decides which token may come next} \\
F_G &= F_{\mathrm{inc}} \setminus \bigl( F_1 \cup \cdots \cup F_k \bigr) && \text{every member decides whether the word may end}
\end{aligned}
```

The asymmetry is what the situation calls for. An exclusion must never restrict the *next* token, because a longer word escapes it: `tiger` is excluded while `tiger2` is fine. An exclusion only ever removes the right to **stop**. So a group whose inclusion accepts while some exclusion also accepts is *blocked*: it withholds the terminating token and stays unfinished, forcing generation onward.

```
t        include accepts, no exclusion does             -> accepted
tiger    include accepts, the `tiger` exclusion does    -> blocked
tiger2   the `tiger` exclusion died on the `2`          -> accepted
```

One fact keeps this cheap. Every member is anchored at the start of the word, so an exclusion that rejects a token can never match again. Exclusion liveness only ever decreases, dead members are dropped and against a real vocabulary nearly all 88 die on the first token.

The trade is explicit. The member automata cost $O\bigl(\sum_i |Q_i|\bigr)$ once and every head shares them; an active name adds only $O(k)$ on top of that, one node id per member still standing, which the dropping drives towards $O(1)$. The alternative is $O\bigl(\prod_i |Q_i|\bigr)$ of automaton, per input, up front.

### 5. The graph: lazy determinization of an automaton nobody can build

Above the indexes sits the syntax graph. It weaves the raw primitives (constants, regexes and groups) together into the overarching SQL grammar.

The grammatical skeleton is right-linear:

```math
\begin{aligned}
S &\to \texttt{SELECT}\; \mathit{Ref} \\
\mathit{Ref} &\to \mathit{field}\; \mathit{More} \;\mid\; \mathit{alias}\,\texttt{.}\,\mathit{field}\; \mathit{More} \\
\mathit{More} &\to \texttt{,}\; \mathit{Ref} \;\mid\; \texttt{FROM}\; \mathit{Entry} \\
\mathit{Entry} &\to \mathit{table}\; \mathit{Head} \;\mid\; \mathit{table}\; \texttt{AS}\; \mathit{alias}\; \mathit{Head} \\
\mathit{Head} &\to \mathit{join}\; \mathit{table}\; \texttt{ON}\; a \;\texttt{=}\; b\; \mathit{Head} \;\mid\; \texttt{,}\; \mathit{Entry} \\
&\;\;\mid\; \texttt{WHERE}\; \mathit{Cond} \;\mid\; \texttt{;} \\
\mathit{Cond} &\to \mathit{operand}\; \mathit{operator}\; \mathit{value}\; \mathit{Done} \\
&\;\;\mid\; \mathit{operand}\; \texttt{IS [NOT] NULL}\; \mathit{Done} \\
\mathit{Done} &\to \texttt{AND}\; \mathit{Cond} \;\mid\; \texttt{OR}\; \mathit{Cond} \;\mid\; \texttt{;}
\end{aligned}
```

Every terminal is an index. An alias is a group, `,` and `;` are regular expressions and everything else is a constant. The one mixed terminal is the $\mathit{value}$ on the right of a condition, which is a constant where it is another column and a regular expression where it is a literal. The whitespace between tokens is a regular expression of its own and is left out of the rules, as are the `AS alias` a joined table may carry, the `NOT` a condition may take and the brackets conditions may nest in.

On its own this grammar could be compiled ahead of time into one large DFA. Four of its nonterminals take their alternatives from the latent context instead. $\mathit{Ref}$ offers only the fields that are still selectable in the current latent state and $\mathit{Entry}$ only the tables that can still answer the selection. Whether $\mathit{Head}$ may take the `;` or has to open another entry depends on what has already been selected. $\mathit{Cond}$ offers the columns the FROM clause actually placed and the type of the chosen column fixes which operators may follow it.

Each of the four is a thunk: hand it the latent context (the constraints on tables, the aliases opened so far, the relation the FROM clause produced) and it answers with the alternatives that context still allows. 

Because of this, the determinized machine is built lazily while it is walked. A **configuration** is a finite set of heads:

```math
\begin{aligned}
\mathcal{C} &= \bigl\{\, (M_i,\; \mathit{ctx}_i,\; k_i) \,\bigr\} && \text{memory, state, continuation} \\
\mathrm{routes}(\mathcal{C}) &= \bigcup_i \mathrm{transitions}(M_i) \\
\mathrm{feed}(\mathcal{C}, v) &= \mathrm{expand}\Bigl( \bigl\{\, (M_i',\; \mathit{ctx}_i,\; k_i) \;:\; M_i' = M_i \text{ after } v, \text{ alive} \,\bigr\} \Bigr)
\end{aligned}
```

$\mathrm{routes}$ evaluates the transition function over the live frontier, performing the subset construction one token at a time instead of tabulating it in advance. $\mathrm{expand}$ resolves the fixpoint: whenever a head reaches the end of its index, it yields its continuation $k_i$, applying it to the updated state $\mathit{ctx}_i$, spawning the next set of required indexes until nothing new appears.

For a fixed schema the language is still regular, so the DFA does exist in theory. But with $n$ tables carrying $2^{2^n}$ boolean functions, plus alias resolutions and join graphs, it is strictly unbuildable, so the determinization stays lazy.

```
NOTE: The layers that meet at a head

A head is one active index and three layers stack at it. Underneath is
the automaton: immutable, positionless, shared by every head walking it.
Over that sits a single walk, private to this head, shaped like the
automaton: a node id for a flat index, or one sub-walk per member for a
group. Over that sits a payload the kernel stores and never opens.

From outside, the loop is: spawn a head with an index and a payload, feed
tokens and when the head reaches the end of its automaton you are handed
your payload back together with the text it matched. Looking up which
grammar rule that was, narrowing the state, producing the next indexes -
all of that happens on the Python side and is invisible here.

The payload is what makes a branch a branch. It carries the state this
branch has committed to and a rule never mutates it; it returns a copy,
so no sibling can observe the choice.
```

### 6. The latent state: semantics as algebra

Every rule runs against a `Context`, which holds what the statement has committed to so far in three structures. `Conflicts` narrows the tables while the fields are selected (6.1, 6.2). `Relationships` is built at `FROM` and connects the tables the fields require (6.3). `Relation` is built at `WHERE` and holds the columns a condition may name (6.4). A rule never changes a context in place. It changes a copy, so branches never see each other's choices.

#### 6.1 Root fields: exactly one, as a polynomial

Write $t_1, \ldots, t_n$ for the tables, each a variable that is $1$ when the table is in the FROM clause. Selecting a root field constrains those variables and the constraint is a Boolean function.

Every Boolean function can be written as a polynomial over $\mathbb{F}_2$, the field with two elements, where **addition is XOR and multiplication is AND**. `Root` works in the ring of such polynomials:

```math
R \;=\; \mathbb{F}_2[t_1, \ldots, t_n] \,\big/\, (t_i^2 - t_i)
```

The quotient says $t^2 = t$: a table is either in the query or not and saying it twice adds nothing.

A field $f$ that lives in the tables $T(f)$ demands that *exactly one of them* is in the FROM clause. As a polynomial that is easy to write for one or two tables and needs correction terms after that:

```math
\begin{aligned}
|T(f)| = 1 : \quad C(f) &= a \\
|T(f)| = 2 : \quad C(f) &= a + b && \text{plain XOR} \\
|T(f)| = 3 : \quad C(f) &= a + b + c \;+\; abc \\
|T(f)| = 4 : \quad C(f) &= a + b + c + d \;+\; abc + abd + acd + bcd
\end{aligned}
```

For two tables, exactly one is XOR. For three, $a + b + c$ over $\mathbb{F}_2$ is the **parity** function, which is $1$ when an odd number of tables are on: right for one table and wrong for all three. The $abc$ term cancels the all-three case and is $0$ everywhere else.

In general $C(f)$ is the sum over **every odd-sized subset** of $T(f)$:

```math
C(f) \;=\; \sum_{\substack{S \subseteq T(f) \\ |S| \text{ odd}}} \;\; \prod_{i \in S} t_i
```

If $m$ tables are on, the terms that survive are the odd-sized subsets of those $m$. For $m \ge 1$ there are $2^{m-1}$ of them, an even number for every $m \ge 2$, so they cancel. The sum is $1$ for $m = 1$ and empty, hence $0$, for $m = 0$.

Selecting a field multiplies its constraint into a running product, which is AND:

```math
P \;\leftarrow\; P \cdot C(f), \qquad P \text{ starts at } 1
```

$P$ is the latent state: the function that is $1$ on exactly those FROM clauses still consistent with everything selected. Every question about the selection is an evaluation of it:

```math
\begin{aligned}
P = 0 \quad&\Longleftrightarrow\quad \text{the selection is contradictory} \\
P|_{t = 1} = 0 \quad&\Longleftrightarrow\quad \text{table } t \text{ contradicts the selection} \\
P|_{t_1 = \cdots = t_n = 0} = 1 \quad&\Longleftrightarrow\quad \text{nothing is outstanding: the query is satisfied} \\
P \cdot C(f) = 0 \quad&\Longleftrightarrow\quad \text{field } f \text{ is excluded} \\
\bigl\{\, t \in \mathrm{vars}(P) \;:\; P|_{t = 1} \neq 0 \,\bigr\} \quad&=\quad \text{the tables still able to satisfy it}
\end{aligned}
```

The last line ranges only over the variables $P$ still mentions. A table $P$ no longer depends on is compatible with the selection but not required by it and only the tables $P$ depends on belong in the FROM clause. Selecting `email` leaves $P = u$, so only `users` is outstanding: `posts` and `comments` pass the $P|_{t=1} \neq 0$ test but do not appear in $P$.

The second line has the opposite problem. A table that has already been named was substituted away and no longer appears in $P$, so the test can never flag it again. The set of excluded tables therefore also holds the tables already used.

Selecting a field twice changes nothing. `body` and `user_id` both live in exactly `{comments, posts}`, so selecting both leaves $P = c + p$ without any special case, because $(c+p)^2 = c+p$.

Naming a table is substitution: setting $u = 1$ satisfies every constraint that mentions `users`. What is left is rarely the constant $1$. Selecting `body` and then naming `posts` leaves $P = c + 1$. It still forbids `comments`, but its value at the origin is $1$ and the origin is where satisfaction is tested.

#### 6.2 Aliased fields: intersection

An alias stands for exactly one table, so its fields only narrow down which table that is and no ring is needed. `Scope` is a plain intersection:

```math
\mathit{cand} \;\leftarrow\; \mathit{cand} \,\cap\, T(f)
```

A field that would empty $\mathit{cand}$ is refused and leaves it unchanged, so $\emptyset$ never means a contradiction. The set becomes empty when the alias's table is named in the FROM clause and that is exactly when the scope is satisfied.

`Scopes` holds one scope per alias and reports an aliased table as the node `"users u"`, so `users` and `users u` stay apart. `Conflicts` puts `Root` and `Scopes` behind one interface.

#### 6.3 The FROM clause: graph contraction

Once the fields are chosen, the required tables have to be **connected**. `Relationships` builds a multigraph whose vertices are the tables (together with aliased nodes like `"users u"`) and whose edges are the foreign keys, each labelled with the column pair it joins on.

One FROM entry is a connected piece being grown from a head vertex $h$. Joining a neighbour $x$ is **vertex contraction**:

```math
\mathrm{join}(h, x) : \qquad G \;\leftarrow\; G \,/\, \{h, x\}
```

Contraction matches SQL's rule: after a join the pair behaves as one relation, every column of either is reachable and the merged vertex has both neighbourhoods. A table two foreign keys away therefore becomes joinable only once the table between them has been joined.

The `ON` columns are the label on the edge, so choosing the target determines them.

```
NOTE: What the join graph answers

Asked what can be joined onto the current entry, it answers with one
neighbouring table per edge, together with the two columns the ON clause
needs. The columns are read off the edge label, which is stored
undirected and turned around when read, so the head's column comes first.

Two tables linked by two different foreign keys have two edges and both
stay, one alternative each. The head is a single vertex, so growing one
FROM entry is a sequence of contractions into it.

Contraction is the only change ever made to the graph and that keeps it
cheap. Nothing is added after the schema has been read, so the contracted
graph is one array saying which vertex each vertex was folded into and
everything else is shared by every copy. A branch that joins nothing
allocates nothing. Loops need no handling either: an edge whose two ends
are in the same class is not reported.
```

#### 6.4 The WHERE clause: closing the clause makes it a table

In 6.1 to 6.3 the fields come first and the tables follow from them. A filter works the other way round. Once `WHERE` is taken the FROM clause is finished, so the columns a condition may name are a fixed set, the **relation**: every column of every node the clause placed, as an entry or through a join.

The relation is built once, when `WHERE` is taken. Two rules decide how each of its columns may be written:

```math
\begin{aligned}
\text{Scoped}(n, col) &= \text{name}(n)\texttt{.}col && \text{always} \\
\text{Root}(col) &\text{ is allowed} \iff \big|\{\, n \in \text{FROM} : col \in n \,\}\big| = 1 && \text{SQL's ambiguity rule}
\end{aligned}
```

$\text{name}(n)$ is the node's alias if it has one and its table name otherwise, the same name the `ON` clause uses. After `FROM users INNER JOIN posts` the relation offers `users.id` and `posts.id` but no bare `id`, while `email` is offered bare because only `users` has it. The count is over the nodes of this FROM clause only: `body` lives on both `posts` and `comments`, yet after `FROM posts` it may be written bare.

The relation does not change once it is built. A filter can neither require a table nor discharge one, so the polynomial and the join graph are frozen at the `WHERE` keyword.

#### 6.5 Conditions: the type rides in the continuation

Every column carries the `Type` the schema parser read. Types fall into six classes and the class of a condition's left operand decides which operators may follow it:

| class | types | operators | literal |
|---|---|---|---|
| numeric | `BIGINT`, `INT`, `DECIMAL`, ... | `=` `!=` `<` `<=` `>` `>=` | `-?[0-9]+(\.[0-9]+)?` |
| text | `VARCHAR`, `TEXT`, `CHAR`, ... | the numeric ones, `LIKE` `NOT LIKE` | `'[^']*'` |
| temporal | `TIMESTAMP`, `DATE`, `TIME`, ... | the numeric ones | `'2024-01-31'`, `'2024-01-31 12:30:00'` |
| boolean | `BOOLEAN`, `BIT` | `=` `!=` | `TRUE`, `FALSE` |
| binary | `BLOB`, `BYTEA`, ... | `=` `!=` | none |
| unknown | a type the parser does not recognise | `=` `!=` | none |

A nullable column also takes `IS NULL` and `IS NOT NULL`, the only operators that end a condition on their own. A primary key is never nullable, whether or not it was declared `NOT NULL`.

The right side of an operator is a literal of the class or another column of the same class that the clause may name, other than the left column itself.

A literal is a pattern that checks only the shape of a value, so `'2024-99-99'` passes as a temporal literal. A class without a literal is compared only with columns of the same class.

The type is not stored in the context. When the operators are offered the left operand has already been written, so its class is a constant of the continuation, the same way the `ON` columns are constants of the join that carries them.

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

The AGPL-3.0 is a strong copyleft license that requires you to release the source code of any modified versions of this software, including when used over a network.
