# oraculum

An SQL autocomplete framework which guarantees grammatical and semantical correctness in the following subset of the language.

```xml
<statement>   := [WITH [RECURSIVE] <definition> [, <definition>]*] <query> ;
<definition>  := <name> [( <name> [, <name>]* )] AS ( <query> )

<query>       := <member> [<set operator> <member>]*
                 [ORDER BY <sort key> [, <sort key>]*] [LIMIT <count> [OFFSET <count>]]
<member>      := SELECT [DISTINCT] <items> FROM <entry> [, <entry>]*
                 [WHERE <filters>] [GROUP BY <keys> [HAVING <filters>]]
<set operator>:= UNION | UNION ALL | INTERSECT | EXCEPT

<items>       := <item> [, <item>]*
<item>        := <value> [AS <name>]
<value>       := <term> [(+ | - | * | /) <term>]*
<term>        := <field ref> | <literal> | <call> | <aggregate> | <ranking> | <case> | <subquery>
<call>        := <scalar>(<value> [, <value>]*) | CAST(<value> AS TEXT)
<scalar>      := ABS | COALESCE | LENGTH | LOWER | ROUND | TRIM | UPPER
<aggregate>   := COUNT(*) | <function>([DISTINCT] <value>) [<window>]
<function>    := COUNT | SUM | AVG | MIN | MAX
<ranking>     := (ROW_NUMBER | RANK | DENSE_RANK)() <window>
<window>      := OVER ([PARTITION BY <field ref> [, ...]] [ORDER BY <field ref> [ASC | DESC] [, ...]])
<case>        := CASE [WHEN <value> (<operator> <value> | IS [NOT] NULL) THEN <value>]+
                 [ELSE <value>] END
<field ref>   := <field> | <alias>.<field>

<entry>       := <source> [<join>]* | <subquery> AS <alias>
<join>        := <join type> <source> ON <column ref> = <column ref>
<source>      := <table> [AS <alias>]
<join type>   := INNER JOIN | LEFT JOIN | RIGHT JOIN | FULL JOIN

<keys>        := <operand> [, <operand>]*
<sort key>    := (<output name> | <operand> | <aggregate>) [ASC | DESC]
<filters>     := <predicate> [(AND | OR) <predicate>]*
<predicate>   := [NOT] (<condition> | "(" <filters> ")")
<condition>   := <operand> <operator> <operand | literal | subquery>
               | <operand> [NOT] BETWEEN <operand | literal> AND <operand | literal>
               | <operand> [NOT] IN (<literal> [, <literal>]* | <query>)
               | <operand> IS [NOT] NULL
               | EXISTS <subquery>
<subquery>    := ( <query> )
<operand>     := <column> | <qualifier>.<column> | <scalar>(<operand>)
               | <aggregate>                                (in HAVING and ORDER BY)
```

## Setup

Needs [Rust](https://rustup.rs), [UV](https://docs.astral.sh/uv/getting-started/installation)
and Python 3.14. Everything else is downloaded at a version this repository
names.

Each project builds itself, from its own directory:

```bash
cd seer
make build       # seer and the kernel, natively
make test        # the corpus, one character at a time, then run in SQLite
make fuzz        # random walks through the graph, checked and run in SQLite
make postgres    # the corpus and the walks, run in PostgreSQL
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

### Layers

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

**The grammar as an NFA:** Wire the keyword constants and identifier patterns as edges in a graph whose shape is the SQL grammar:

```mermaid
graph LR
    q0(( )) -->|"SELECT"| q1(( ))
    q1 -->|"field"| q2(( ))
    q2 -->|","| q1
    q2 -->|"FROM"| q3(( ))
    q3 -->|"table"| q4(( ))
    q4 -->|"join .. on .."| q4
    q4 -->|","| q3
    q4 -->|"WHERE"| q5(( ))
    q5 -->|"condition"| q6(( ))
    q6 -->|"AND / OR"| q5
    q4 -->|";"| q7(((end)))
    q6 -->|";"| q7

    classDef plain fill:#4a5160,stroke:#2f343f,color:#ffffff
    classDef accent fill:#2f6fb5,stroke:#1b4670,color:#ffffff
    class q0,q1,q2,q3,q4,q5,q6 plain
    class q7 accent
```

Every edge label is one of the automata from the previous step: a constant, a pattern or a difference of patterns. Walking an edge means feeding tokens into that automaton until it accepts, then following the grammar arc. Multiple edges out of one node are multiple live branches, which makes the graph an NFA. The system determinises lazily, one token at a time, rather than building the exponential product machine up front.

**Latent state: enabling and disabling routes:** The grammar graph is static: it knows that *a* field follows `SELECT` and *a* table follows `FROM`, but not which ones. A second layer, the latent state, rides alongside the walk and gates edges as the query grows.

Take a minimal schema:

| table | fields |
|---|---|
| **t1** | f1, f2, f3 |
| **t2** | f4, f2, f5 |

Suppose `f1` and `f2` have been selected. `f1` lives only in `t1`, so `t1` is required. `f2` lives in both, so writing it root means exactly one table may supply it and `t2` is ruled out: with both tables in the query the root `f2` would be ambiguous. Every route that needs `t2` is disabled:

```mermaid
graph LR
    q1(["next field"]) -->|"f2"| q2(( ))
    q1 -->|"f3"| q2
    q1 -.->|"f4"| q2
    q1 -.->|"f5"| q2
    q2 -->|"FROM"| q3(( ))
    q3 -->|"t1"| q4(( ))
    q3 -.->|"t2"| q4
    q4 -->|";"| q5(((end)))

    classDef plain fill:#4a5160,stroke:#2f343f,color:#ffffff
    classDef accent fill:#2f6fb5,stroke:#1b4670,color:#ffffff
    class q1,q2,q3,q4 plain
    class q5 accent
```

Solid edges are live, dashed edges are disabled. `f4` and `f5` belong to `t2` alone, so both are withdrawn; `t2` stops being offered as a FROM target. `f2` survives because `t1` has it too.

**Conflict management as Boolean algebra:** The gating is computed in $\mathbb{F}_2$, the two-element field where addition is XOR and multiplication is AND. Each field carries a constraint polynomial encoding "exactly one of my tables supplies me":

```math
C(\text{f1}) = t_1 \qquad C(\text{f2}) = t_1 + t_2 \qquad C(\text{f5}) = t_2
```

$C(\text{f2}) = t_1 + t_2$ is XOR: exactly one of the two must supply it. Selecting a field multiplies its constraint into a running product $P$:

```math
P \;\leftarrow\; 1 \;\cdot\; C(\text{f1}) \;\cdot\; C(\text{f2}) \;=\; t_1(t_1 + t_2) \;=\; t_1 + t_1 t_2
```

using $t_1^2 = t_1$ in $\mathbb{F}_2$. Evaluating $P$ answers every question the grammar needs:

| evaluation | result | meaning |
|---|---|---|
| $P$ at $t_1{=}1,\; t_2{=}0$ | $1$ | `FROM t1` works |
| $P$ at $t_1{=}0,\; t_2{=}1$ | $0$ | `FROM t2` alone contradicts the selection |
| $P$ at $t_1{=}1,\; t_2{=}1$ | $0$ | both tables, but root `f2` becomes ambiguous |
| $P \cdot C(\text{f5})$ | $0$ | `f5` can no longer be selected |

The last two rows are worth pausing on. Having both tables makes the root `f2` ambiguous, since each would claim it, so the polynomial zeros out. And $P \cdot C(\text{f5}) = (t_1 + t_1 t_2) \cdot t_2 = t_1 t_2 + t_1 t_2 = 0$ in $\mathbb{F}_2$: the product kills it outright, so `f5` is never offered. The polynomial decides without enumeration which tables, fields and routes remain viable.

**The join graph.** When two tables are both required, say after selecting `f1` and `f5` instead, which gives $P = t_1 \cdot t_2$, the FROM clause must connect them. Foreign keys form a graph whose edges carry the columns to join on:

```mermaid
graph LR
    T1["t1 (f1, f2, f3)"] ---|"t1.f1 = t2.f4"| T2["t2 (f4, f2, f5)"]

    classDef plain fill:#4a5160,stroke:#2f343f,color:#ffffff
    class T1,T2 plain
```

The edge label determines the `ON` clause. The schema writes it; the model only picks which edge to walk. Joining is vertex contraction: `t1` and `t2` merge into one node that inherits both neighbourhoods, so a table two foreign keys away becomes reachable only after the intermediate one has been joined in. With more tables the problem is which contraction sequence connects the required set and the edges fix every `ON` clause along the way.

**The WHERE clause: a phase boundary.** Everything above runs in one direction: fields are chosen, tables follow, joins connect them. The `WHERE` keyword reverses the flow. By the time it is reached the FROM clause is finished and what a condition may name is no longer something to be solved: it is a fixed set. Call it the **virtual table**: every column of every source the clause placed, whether it arrived as a root entry or was contracted in by a join.

Continuing the example, suppose the FROM clause settled on `t1 INNER JOIN t2 ON t1.f1 = t2.f4`. The virtual table is:

| reference | columns |
|---|---|
| `t1` | f1, f2, f3 |
| `t2` | f4, f2, f5 |

A column reachable as `t1.f1` is always offered scoped. A column like `f3` is offered root too, because exactly one source supplies it. But `f2` lives in both, so it can only be written as `t1.f2` or `t2.f2`: root `f2` would be ambiguous. This is SQL's own resolution rule, applied to the nodes of *this clause* rather than to the whole schema.

On top of that sits the type, which dictates the permitted operators and whether the right-hand side can be a literal pattern or another column of the same class.

The key property is that the WHERE clause **never feeds back**. A filter can neither require a table nor discharge one, so the polynomial $P$ and the join graph are frozen at the `WHERE` boundary. Conditions combine with `AND` and `OR`, take a `NOT` and nest behind brackets, but nothing they say alters which tables are in the query.

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

**Aggregates and grouping:** An item may also be an aggregate over a column,
`COUNT(*)` included, optionally named with `AS`. The function decides which
columns it may take: `SUM` and `AVG` only numbers, `MIN` and `MAX` anything with
an order, `COUNT` everything. A column handed to a function narrows the tables
like any other column, but harder: `SUM(id)` may only be supplied by a table
whose `id` is numeric.

```sql
SELECT COUNT(*) FROM users;
SELECT MIN(title), MAX(published_at) FROM posts;
SELECT user_id, COUNT(*) AS n FROM posts GROUP BY user_id;
```

Once any item aggregates, every plain item has to be grouped, and the statement
cannot end until it is. A key is a column of the relation the FROM clause
produced, so `GROUP BY email` and `GROUP BY u.email` are the same key where one
source supplies `email`. HAVING follows with the condition grammar of WHERE,
over the grouped columns and aggregates of any column:

```sql
SELECT u.email, COUNT(p.id) AS posts_count
FROM users AS u
INNER JOIN posts AS p ON u.id = p.user_id
GROUP BY u.email
HAVING COUNT(p.id) >= 2;
```

**WITH: queries stacked on queries:** A statement may open with definitions,
each a query of its own whose result is a table to everything after it. A
definition's columns are its items, so they need names that differ: every
computed item is named and no name comes twice. A projected column keeps the
foreign key it had, so the join graph runs through a definition as through the
table it came from:

```sql
WITH c AS (SELECT user_id, COUNT(*) AS n FROM posts GROUP BY user_id)
SELECT email, n FROM users INNER JOIN c ON users.id = c.user_id WHERE n > 1;
```

Every name a definition introduces, its own and its columns', is reserved
from then on, in every spelling, since SQL hears `T` and `t` as one name.
Section 6.6 is the grouping, 6.7 the stack definitions build and 6.8 the names it reserves.

A column list names the columns instead, so the body needs no names of its
own, only as many items as the list has names:

```sql
WITH authors(author, n) AS (SELECT user_id, COUNT(*) FROM posts GROUP BY user_id)
SELECT email, n FROM users INNER JOIN authors ON users.id = authors.author;
```

**Expressions:** An item is any value: a column, a literal, a scalar function
over values, arithmetic, a `CASE`, an aggregate over a value, a window. Every
function says what it accepts, so `LOWER(` only offers what can be text and
`id + ` only what can be a number, and every item may be named:

```sql
SELECT LOWER(email) AS mail, LENGTH(TRIM(last_name)), id + 1 FROM users;
SELECT COALESCE(verified, FALSE), CAST(created_at AS TEXT) FROM users;
SELECT CASE WHEN verified IS NULL THEN 'unknown' ELSE 'known' END AS state FROM users;
SELECT COUNT(DISTINCT user_id), SUM(CASE WHEN published_at IS NULL THEN 1 ELSE 0 END) FROM posts;
```

A grouping key may be an expression too, and grouping covers whatever is built
from grouped values alone: `LOWER(email)` over `GROUP BY email`, but `email`
not over `GROUP BY LOWER(email)`:

```sql
SELECT LOWER(email), COUNT(*) FROM users GROUP BY LOWER(email);
SELECT user_id, COUNT(*) + 1, RANK() OVER (ORDER BY user_id) FROM posts GROUP BY user_id;
```

**Conditions, sorting and limits:** A condition may range with `BETWEEN`, test
membership with `IN`, and take a scalar function on its left. After the body
come `ORDER BY` and `LIMIT`, sorting by whatever the result can be sorted by:
any value of a plain query, the grouped values and aggregates of a grouped
one, and the output names of a `SELECT DISTINCT`:

```sql
SELECT email FROM users WHERE users.id IN (1, 2, 3) AND created_at BETWEEN '2024-01-01' AND '2024-12-31';
SELECT user_id, COUNT(*) AS n FROM posts GROUP BY user_id ORDER BY n DESC LIMIT 3 OFFSET 1;
SELECT DISTINCT LOWER(email) AS e FROM users ORDER BY e;
```

**Compounds:** Members joined by `UNION`, `UNION ALL`, `INTERSECT` and `EXCEPT`
produce the first member's columns, each as many and of the same class, and the
compound is sorted and limited after its last member, by the first member's
names:

```sql
SELECT email AS label FROM users UNION SELECT title FROM posts ORDER BY label LIMIT 5;
```

**Recursion:** Under `WITH RECURSIVE` a member after a union may read the
definition it belongs to, as the members before it produced it. That member
stays a simple select - no aggregate, window, `DISTINCT`, grouping or sorting,
the definition read once and by inner joins only - and it is the last:

```sql
WITH RECURSIVE t(n) AS (SELECT 1 FROM users UNION ALL SELECT n + 1 FROM t WHERE n < 3)
SELECT n FROM t;
```

**Subqueries:** A query may stand inside another: as the one value a
comparison takes, as the list of an `IN`, after `EXISTS`, as a value of the
projection and as a table of the FROM clause. One inside a condition reads the
columns of the query around it, qualified, which is what makes it correlated:

```sql
SELECT email FROM users WHERE EXISTS (SELECT title FROM posts WHERE posts.user_id = users.id);
SELECT title FROM posts WHERE published_at > (SELECT MIN(created_at) FROM users WHERE users.id = posts.user_id);
SELECT email, (SELECT COUNT(*) FROM posts) AS total FROM users;
SELECT d.user_id FROM (SELECT user_id, COUNT(*) AS n FROM posts GROUP BY user_id) AS d WHERE d.n > 1;
```

A value is one row of one column, so its query aggregates and does not group.
A derived table is read through its alias, and has to export what the
projection already read off it.

Section 6.9 is how expressions are written before the FROM clause exists, 6.10
the placement rule aliases add to it, 6.11 sorting, 6.12 compounds and
recursion, and 6.13 subqueries.

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

```mermaid
graph LR
    q0(( )) -->|SELECT| ref

    ref(["next field"]) ==>|alias| q1(( ))
    q1 -->|"."| q2(( ))
    q2 -->|field| more(["after a field"])
    ref -->|field| more

    more -.->|","| ref
    more -->|FROM| entry

    entry(["next table"]) -->|table| head(["current entry"])
    entry -->|"table AS alias"| head

    head -->|"join type"| j1(( ))
    j1 -->|table| j2(( ))
    j2 -->|ON| j3(( ))
    j3 -->|"a = b"| head

    head -.->|","| entry
    head -.->|";"| accept(((accept)))

    head -->|WHERE| cond
    cond(["next condition"]) -->|operand| w1(( ))
    w1 -->|"operator"| w2(( ))
    w2 -->|"operand or literal"| done(["after a condition"])
    w1 -->|"IS [NOT] NULL"| done

    done -->|"AND, OR"| cond
    done -.->|";"| accept

    classDef plain fill:#4a5160,stroke:#2f343f,color:#ffffff
    classDef accent fill:#2f6fb5,stroke:#1b4670,color:#ffffff
    class q0,q1,q2,more,j1,j2,j3,w1,w2,done,accept plain
    class ref,entry,head,cond accent
```

Solid edges are lattices, dashed ones expressions and the thick one is the alias group. The whitespace between tokens is an expression index of its own and is left out of the picture, as are the `AS alias` a join target may carry, the `NOT` prefix a condition may take and the brackets it may nest behind. The one mixed edge is the right hand side of a condition, which is a lattice where it is another column and an expression where it is a literal.

If it were just this static structure, the language could be compiled ahead of time into one massive DFA. 

But it isn't static. The four heavy states are the ones whose alternatives come from the latent context rather than from the grammar. Whether `head` may take the `;` or has to open another table entry depends on what has *already been selected*, the `field` edge out of `ref` ranges over the fields that are *still selectable in the current latent state* and the `operand` edge out of `cond` ranges over the columns the FROM clause *actually placed*, with the operator that follows it fixed by that column's type. 

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

The state each rule is run against is a `Context`. It carries everything the statement has committed to so far: the stack of definitions closed so far and the query being written over it. Every operation that changes it works on a copy, so branches never see each other.

The query is a **virtual table**, the one object that owns the data structure of a SELECT as it is written. It is held in one part per stretch of its lifecycle (the selection while the projection is written, the sources while the FROM clause is placed, the refinement written against the closed relation afterwards, the presentation once the body is complete), and the parts are bound together by a state machine whose transitions fall on keywords:

```mermaid
stateDiagram-v2
    direction LR
    [*] --> PROJECTION
    PROJECTION --> SOURCE: FROM
    SOURCE --> FILTER: WHERE
    SOURCE --> GROUPING: GROUP BY
    FILTER --> GROUPING: GROUP BY
    GROUPING --> HAVING: HAVING
    state body <<choice>>
    SOURCE --> body
    FILTER --> body
    GROUPING --> body
    HAVING --> body
    body --> ORDERING: ORDER BY
    body --> LIMITING: LIMIT
    ORDERING --> LIMITING: LIMIT
    body --> CLOSED: ; ) or a set operator
    ORDERING --> CLOSED: ; or )
    LIMITING --> CLOSED: ; or )
    CLOSED --> [*]
```

Entering SOURCE builds the join graph and leaving it builds the relation; leaving the body fixes the result, which the presentation sorts and a definition exports. Which of the drawn moves a query may take is decided in one place, and it is where the rules spanning parts live: the projection has to be complete before FROM, the body complete before anything after it (its FROM clause supplying what the projection demanded, its grouping covering every item), and a recursive member never groups, sorts or limits.

The statement has a machine of its own one level up, `PREAMBLE -> DECLARATION -> DEFINITION -> PREAMBLE -> ... -> MAIN`, which only says which query is open: a definition is declared (its name, its column list) and then opened at the `SELECT` of its body. A compound query runs one clause machine per member, each ended by the set operator that opens the next. Both machines are tables of legal moves and nothing else: what a move builds is the virtual table's business, so the lifecycle can be read without the work getting in the way.

#### 6.1 Root fields: exactly one, as a polynomial

Write $t_1, \ldots, t_n$ for the tables, each a variable that is $1$ when the table is in the FROM clause. Selecting a root field constrains those variables and the constraint is a Boolean function.

The natural home for Boolean functions here is $\mathbb{F}_2$, the field with two elements, where **addition is XOR and multiplication is AND**. `Root` works in the ring of such functions:

```math
R \;=\; \mathbb{F}_2[t_1, \ldots, t_n] \,\big/\, (t_i^2 - t_i)
```

The quotient says $t^2 = t$: a table is either in the query or not and saying it twice adds nothing.

A field $f$ that lives in the tables $T(f)$ says *exactly one of those is where it came from*. Writing that as a polynomial is easy for one or two tables and gets interesting after:

```math
\begin{aligned}
|T(f)| = 1 : \quad C(f) &= a \\
|T(f)| = 2 : \quad C(f) &= a + b && \text{plain XOR} \\
|T(f)| = 3 : \quad C(f) &= a + b + c \;+\; abc \\
|T(f)| = 4 : \quad C(f) &= a + b + c + d \;+\; abc + abd + acd + bcd
\end{aligned}
```

For two tables, "exactly one" *is* XOR. For three it is not: $a + b + c$ over $\mathbb{F}_2$ is the **parity** function, which is $1$ when an odd number of tables are on. That is right for one table and wrong for three. The $abc$ term is there to cancel the all-three case and nothing else, since it is $0$ everywhere else.

The pattern that falls out is clean. $C(f)$ is the sum of **every odd-sized subset** of $T(f)$:

```math
C(f) \;=\; \sum_{\substack{S \subseteq T(f) \\ |S| \text{ odd}}} \;\; \prod_{i \in S} t_i
```

and it is exactly-one for a one-line reason: if $m$ tables are on, the terms that survive are the odd-sized subsets of those $m$ and for $m \ge 1$ there are $2^{m-1}$ of them, which is even for every $m \ge 2$, so they cancel. The sum is $1$ only when $m = 1$ and empty, hence $0$, when $m = 0$.

Selecting a field multiplies its constraint into a running product, which is AND:

```math
P \;\leftarrow\; P \cdot C(f), \qquad P \text{ starts at } 1
```

$P$ is the latent state: the function that is $1$ on exactly those FROM clauses still consistent with everything selected. Every question is now an evaluation of it:

```math
\begin{aligned}
P = 0 \quad&\Longleftrightarrow\quad \text{the selection is contradictory} \\
P|_{t = 1} = 0 \quad&\Longleftrightarrow\quad \text{table } t \text{ contradicts the selection} \\
P|_{t_1 = \cdots = t_n = 0} = 1 \quad&\Longleftrightarrow\quad \text{nothing is outstanding: the query is satisfied} \\
P \cdot C(f) = 0 \quad&\Longleftrightarrow\quad \text{field } f \text{ is excluded} \\
\bigl\{\, t \in \mathrm{vars}(P) \;:\; P|_{t = 1} \neq 0 \,\bigr\} \quad&=\quad \text{the tables still able to satisfy it}
\end{aligned}
```

Two of those lines need care. The last one ranges over the variables $P$ still mentions rather than over every table: a table $P$ has stopped depending on is *compatible* with the selection but not *required* by it and only what $P$ still depends on belongs in the FROM clause. Selecting `email` leaves $P = u$ and it is `users` alone that is outstanding: `posts` and `comments` pass the $P|_{t=1} \neq 0$ test yet appear nowhere in $P$. The second line has the mirror image of the same subtlety: a table already named has been substituted away and no longer appears in $P$, so the test can never flag it again and the excluded set carries the used tables alongside.

Idempotence earns its keep. Selecting `body` and then `user_id`, both living in exactly `{comments, posts}`, leaves $P = c + p$ unchanged, because $(c+p)^2 = c+p$: the second field adds no information and the algebra says so with no special case. Naming a table is substitution: setting $u = 1$ discharges the demand of every constraint mentioning it. What is left is rarely the constant $1$. Selecting `body` and then naming `posts` leaves $P = c + 1$, which goes on forbidding `comments`, yet its value at the origin is $1$ and that evaluation is what satisfaction tests.

#### 6.2 Aliased fields: intersection

An alias denotes **exactly one** table and cannot be two things at once, which removes all the cross-talk the ring was needed for. `Scope` is then a plain intersection:

```math
\mathit{cand} \;\leftarrow\; \mathit{cand} \,\cap\, T(f)
```

A selection that would empty $\mathit{cand}$ is refused outright and leaves it untouched, so $\emptyset$ never means contradiction: it is what naming the table produces and it is exactly the condition for the scope being satisfied. `Scopes` is the registry of them, reporting an aliased table as the scoped node `"users u"` so that `users` and `users u` stay distinguishable downstream. `Conflicts` is the facade over both halves.

#### 6.3 The FROM clause: graph contraction

Once the fields are chosen, the required tables have to be **connected**. `Relationships` builds a multigraph whose vertices are the tables (together with aliased nodes like `"users u"`) and whose edges are the foreign keys, each labelled with the column pair it joins on.

One FROM entry is a connected piece being grown from a head vertex $h$. Joining a neighbour $x$ is **vertex contraction**:

```math
\mathrm{join}(h, x) : \qquad G \;\leftarrow\; G \,/\, \{h, x\}
```

Contraction is the right operation because it reproduces SQL's own rule: after a join the pair behaves as one relation, every column of either is reachable and the merged vertex inherits both neighbourhoods, so a table two foreign keys away only becomes joinable once the table between them has been joined in.

The `ON` columns are the label on the edge, so choosing the target determines them.

```
NOTE: What the join graph answers

Ask it what can be joined onto the current entry and you get back, per
edge, the neighbouring table together with the two columns the ON clause
needs. Those are read off the edge label. The label is stored undirected
and oriented when asked, so the head's column always comes out first.

It is a multigraph deliberately: two tables joined by two different
foreign keys are two alternatives and both stay. The head is a single
vertex name, so growing one FROM entry is a sequence of contractions
into it.

Contraction being the *only* mutation is worth saying out loud, because
it is what makes the structure cheap. Nothing is ever added after the
schema has been read, so the quotient is determined by one array, saying
which vertex each vertex has been folded into; everything else is shared
by every copy. A branch that joins nothing allocates nothing and
a dropped loop needs no handling: an edge whose far end is in the same
class as its near end is simply not reported.
```

#### 6.4 The WHERE clause: closing the clause makes it a table

Sections 6.1 to 6.3 run forwards: fields are chosen first and the tables follow. A filter runs the other way. Once `WHERE` is taken the FROM clause is finished, so what a condition may name is no longer a constraint to be solved but a fixed set: the **relation**, every column of every node the clause placed, whether the node came in as an entry or through a join.

The relation is built once, when SOURCE is left, and two counting rules decide how each of its columns may be written:

```math
\begin{aligned}
\text{Scoped}(n, col) &= \text{name}(n)\texttt{.}col && \text{always} \\
\text{Root}(col) &\text{ is allowed} \iff \big|\{\, n \in \text{FROM} : col \in n \,\}\big| = 1 && \text{SQL's ambiguity rule}
\end{aligned}
```

$\text{name}(n)$ is the alias where the node has one and the table name otherwise, the same name the `ON` clause is written with. After `FROM users INNER JOIN posts` the relation offers `users.id` and `posts.id` but no bare `id`, while `email` is offered bare because only `users` has it. The count runs over the nodes of this clause, not over the schema: `body` lives on both `posts` and `comments`, yet `FROM posts` alone may write it bare.

An outer join can pad a node with NULLs, so every column of a padded node is nullable in the relation, whatever the schema says about it.

Nothing written after the FROM clause changes it: the polynomial and the join graph are frozen once SOURCE is left, whether `WHERE`, `GROUP BY` or the end of the body comes next.

#### 6.5 Conditions: the type rides in the continuation

Every column carries the `Type` the schema parser read and conditions are where it is used. Types fall into six classes and the class of the left operand decides which operators may follow it:

| class | types | operators | literal |
|---|---|---|---|
| numeric | `BIGINT`, `INT`, `DECIMAL`, ... | `=` `!=` `<` `<=` `>` `>=` `[NOT] BETWEEN` `[NOT] IN` | `-?[0-9]+(\.[0-9]+)?` |
| text | `VARCHAR`, `TEXT`, `CHAR`, ... | the numeric ones, `LIKE` `NOT LIKE` | `'[^']*'` |
| temporal | `TIMESTAMP`, `DATE`, `TIME`, ... | the numeric ones | `'2024-01-31'`, `'2024-01-31 12:30:00'` |
| boolean | `BOOLEAN`, `BIT` | `=` `!=` | `TRUE`, `FALSE` |
| binary | `BLOB`, `BYTEA`, ... | `=` `!=` | none |
| unknown | a type the parser does not recognise | `=` `!=` | none |

A nullable column also takes `IS NULL` and `IS NOT NULL`, the only operators that end a condition by themselves. A primary key is never nullable, whether or not it was written `NOT NULL`.

What stands on the right of an operator is a literal of the class, or another value of the same class that the clause may name, but never the left value itself. `=`, `!=` and the orderings may also compare with a scalar subquery (6.13). `BETWEEN` takes two such values and `IN` a list of literals or a subquery.

A literal is a pattern: it fixes the shape and never the value, so `'2024-99-99'` is a temporal literal as far as the grammar is concerned. A class without a literal is compared with columns of the same class only. A binary or unknown column with no such column opposite it takes no operator other than the `IS NULL` pair, and a column that takes no operator at all is not offered as the left operand.

The type is never stored in the context. When the operators are offered the left operand is already written, so its class is a constant of the continuation, the same way the `ON` columns are constants of the join clause that carries them.

#### 6.6 Aggregates and grouping: typed fields and coverage

An aggregate's argument is a field like any other, so it constrains the tables the way 6.1 does, with one more condition: the column has to be of a class the function accepts. Write $T(f)$ for the tables that have a field $f$ and $T_K(f)$ for those where it is of a class in $K$. The argument has to come from one of $T_K(f)$ and the other owners may not be in the clause at all, or the bare name would be ambiguous between them:

```math
C_K(f) \;=\; C\bigl(T_K(f)\bigr) \cdot \prod_{t \,\in\, T(f) \setminus T_K(f)} (1 + t)
```

$(1 + t)$ is $1$ exactly when $t$ is absent. When every owner qualifies the product is empty and $C_K(f) = C(f)$. One set of these constraints is built for each class set a position asks for (numeric for `SUM` and `AVG`, ordered for `MIN` and `MAX`, text for `LOWER`), the first time it is asked for. An aliased argument intersects its scope with $T_K(f)$ instead.

An aggregate is also a column. Its function maps the argument's `Field` to the `Field` it produces: `COUNT` to a number that is never NULL, `MAX(created_at)` to a timestamp that may be. This is what HAVING compares, with the operators of 6.5, and what a definition exports.

Grouping is written against the relation, so a key is a value of it: a column or a scalar function over columns. Every value has a **key** that all of its spellings share. A column is keyed by the node that supplies it, so `email` and `users.email` have one key, and a call is keyed by its function and the keys of its arguments. Once the relation is closed the items of the projection resolve to the same keys, and coverage becomes a recursive question about values:

```math
\text{covered}(v) \iff \text{key}(v) \in \text{keys} \;\lor\; v \text{ is an aggregate or a constant}
\;\lor\; \bigl(v \text{ is not a column} \land \forall\, c \in \text{children}(v) : \text{covered}(c)\bigr)
```

A query that aggregates, because it groups or because an item holds an aggregate, may only leave its body once every item is covered. `LOWER(email)` is covered by `GROUP BY email` because its child is. `email` is not covered by `GROUP BY LOWER(email)`, because it is a column and its key is not grouped. A window is not an aggregate, so its arguments and keys need covering like any other value of the row. The check is done where the body is left, so the terminator, `ORDER BY`, `LIMIT`, a set operator and a closing bracket are not offered until every item is covered.

Two nodes of one table, `users` and `users AS u`, are one variable to the algebra, yet a bare column would be ambiguous between them. Placing a node therefore checks that every bare column keeps a single supplier, and the same check filters what is offered (6.10).

#### 6.7 WITH: a stack of virtual tables

A definition is a query of its own and once it closes it is a table. A statement with definitions is a stack: each definition is written over everything defined before it and the main query over all of them.

```mermaid
graph LR
    main(["main query"]) -->|"stacked on"| b(["b"])
    b -->|"stacked on"| a(["a"])
    a -->|"stacked on"| schema(["the schema"])

    classDef plain fill:#4a5160,stroke:#2f343f,color:#ffffff
    classDef accent fill:#2f6fb5,stroke:#1b4670,color:#ffffff
    class a,b,schema plain
    class main accent
```

Every virtual table holds the stack below it as a `Catalog`. The catalog folds the stack into the two things a query needs: one schema with the physical tables and every definition below, and the reserved names of every layer (6.8). The resolvers of 6.1 to 6.6 run over that schema unchanged. A definition is a `Table` like any the schema declared: the algebra gets one more variable, the join graph one more vertex and the relation one more source.

When a definition closes it exports one column per item, under the item's output name. A plain column keeps its type, its nullability, its foreign key and its **origin**, the schema column it is. A foreign key matches its target by origin rather than by table name, so the key from `posts.user_id` to `users(id)` reaches the `id` of any definition that projected `users.id`, and a definition that projected `posts.user_id` still joins `users`. A computed value has no origin, so nothing joins through it.

A closed virtual table never changes, so the stack is persistent. Pushing a definition builds a new catalog over the old one, and every branch of the syntax graph shares the layers below the query it is writing.

#### 6.8 Reserved names: every spelling, at every level

An invented name is an identifier minus a reserved set (section 4) and the set is assembled from the stack. Its base is the same for every name: the keywords, the function names and every table and column any layer defines. The keywords are not only the grammar's own. A statement has to run where it is sent and a dialect refuses an unquoted alias that spells one of its keywords (SQLite `NOTHING`, PostgreSQL `USER`), so the set holds every keyword SQLite knows and every word PostgreSQL reserves. On top of the base, each use adds what the query has introduced itself:

| the name being invented | may additionally not be |
|---|---|
| an alias, `u.` in the projection | an output name; an alias already opened, unless it is written exactly as before |
| an output name, `AS n` | another output name; any alias |
| a definition, `WITH c` | anything the stack defines, earlier definitions included |
| a column of a definition's list, `WITH c(a, b)` | the definition's name; another name of the list |
| anything inside a definition | the definition's own name |
| anything inside a subquery | an alias or output name of the queries around it |

SQL compares unquoted identifiers ignoring case, so each reserved name is excluded by a case-insensitive pattern: `USERS` is the table, `Select` is the keyword and two definitions called `T` and `t` collide. An alias that is already open may be written again, since it is the same scope, but only where it still has a column to offer and only in the spelling it was opened with. Its exclusion is every case of it minus that one spelling, a difference nested inside the group's own difference.

#### 6.9 Expressions: written before the FROM clause exists

The projection is written before anything says which table a column comes from, so an item cannot be typed the way a condition is. It can be constrained instead. Every value is written at a **position** that says which classes it may have, how many calls may still nest inside it, whether an aggregate or a window may stand there and whether it reads the row, is a constant or has to hold an aggregate. `LOWER(` writes its argument at a text position, so a column there is demanded with $C_{\{\text{text}\}}(f)$ of 6.6 and only columns some table can supply as text are offered. A function is only offered where something can be written inside it: an item of a scalar subquery has to hold an aggregate, so a function is offered there only while an aggregate still fits inside it.

A value's class is either fixed by its shape (`LOWER(...)` is text, `id + 1` and `COUNT(*)` are numeric) or follows other values (`MAX(x)` has the class of `x`, `COALESCE(x, y)` the class of both), down to the columns, which are the only thing still open. That gives every value a **narrowing**: the columns that have to be of a class for the value to be of it. A value written where its class was free is narrowed when something asks for one, by demanding its columns again under the narrower class:

```math
P \;\leftarrow\; P \cdot C_K(f) \qquad\text{and}\qquad C(f) \cdot C_K(f) = C_K(f)
```

since $C_K(f)$ implies $C(f)$. `id + ` narrows `id` to numeric at the `+`, and a comparison inside a `CASE` narrows its left side to the class it compares in. The operator is only offered where the narrowed product is still non-zero.

The tree of a value is never stored half built. Every emitter takes a continuation that is handed the finished value, so each branch of the graph carries what it has written in the closures ahead of it and the virtual table learns of an item only when it is complete. The item's last token is not that moment, because `id` may still become `id + 1`. The moment is the separator after it, the comma or the whitespace before `AS` or `FROM`, and both readings live on as separate heads until the next character tells them apart:

```mermaid
graph LR
    id(["id"]) -->|"␣ (commits id)"| a(["AS / FROM"])
    id -->|"␣+␣"| plus(["a numeric term"])
    id -->|", (commits id)"| next(["the next item"])
    plus -->|"…"| tail(["id + 1"])

    classDef plain fill:#4a5160,stroke:#2f343f,color:#ffffff
    classDef accent fill:#2f6fb5,stroke:#1b4670,color:#ffffff
    class id,a,plus,next plain
    class tail accent
```

What the separator may be is decided before the item is committed. An item of a definition that has no name of its own, or whose name another item already has, is only offered `AS`. After the FROM clause the same functions are written over the relation, where every column has a type, so they are typed as they are written and a call over columns is an operand just like a column.

#### 6.10 Placement: aliases are nodes too

The algebra decides which tables the bare columns need and each alias scope decides which table its alias may be. Neither sees the rule SQL applies across both: a bare column has exactly one supplier among the nodes of the FROM clause, and every alias is a node that will be placed. `SELECT email, u.first_name` leaves exactly one FROM clause, `users AS u` alone, because a bare `users` beside it would make `email` ambiguous. `SELECT id, title, u.email` leaves none: `title` needs `posts`, `u.email` needs `users` and both supply `id`.

**Placeability** asks whether a FROM clause can still be written: is there a table for every alias not placed yet and a set of the tables the algebra still requires, so that no bare column has two suppliers among them and the nodes already placed, and the product holds with all of them present? Two facts keep the search small, however many aliases are open:

- Where an alias may still be a derived table (6.13), being one is its best option. A derived table supplies no bare column and asserts nothing to the algebra, so whatever a real table would let the rest of the clause complete with, a derived table would too. Where every alias may be derived, only the algebra is left to ask.
- Otherwise each alias is given one of its tables in turn, and what the rest of the search can still do depends only on the set of tables given so far. A set that failed once is not tried again.

The projection offers a column only where the answer stays yes, a new alias only where some column would, and the FROM clause places a node only where it does. A statement is never written into a FROM clause that waits for a node it can never place.

#### 6.11 Sorting: what the result can still be sorted by

`ORDER BY` and `LIMIT` are written once the body is complete, against its result. What a key may be depends on what the result is:

| the result | may be sorted by |
|---|---|
| a plain query | any value of the relation, a function over one, an output name |
| an aggregated one | the grouped values, functions over them, any aggregate, an output name |
| `SELECT DISTINCT` | its output names |
| a compound | the output names of its first member |

An output name is only offered where exactly one item goes by it, since a name two items share is ambiguous. Outside a compound it also has to be an `AS` alias, or a bare column name that still means the column it came from, because SQLite reads any other name as a column of the relation. An output name is always written whole and never inside a function: PostgreSQL reads `ORDER BY e` as the output `e`, but `UPPER(e)` as a column that does not exist.

A column or output already sorted by is not offered again, however it is spelled. `ORDER BY`, and the comma before each further key, are only offered while something is left to sort by. `LIMIT` and `OFFSET` take a count each, `OFFSET` only after `LIMIT`.

#### 6.12 Compounds and recursion: siblings, and a layer read before it closes

The members of a compound are siblings, not a stack: each is a query of its own over the same catalog and none of them reads another. What ties them together is their result. The first member fixes a **shape**, its arity and the class of each column, and every later member is written under it: its items are offered at positions of those classes and `FROM` only once it has as many. A definition's column list is a shape too, of arity alone.

The compound's result merges the members' results. It takes the names of the first member, it is NULL wherever any member may be, and it keeps a lineage only where the members agree on whose values a column holds. A column that is `users.id` in one member and `posts.user_id` (a key pointing at `users.id`) in the next holds user ids either way, so it stays joinable from every key that points at `users`. A column that is `users.id` in one member and `posts.id` in the next holds nothing in particular, and nothing joins through it.

A recursive definition reads itself before it is closed, which a stack of closed layers cannot express. The catalog a recursive member is written over therefore carries one **provisional** table besides its layers: the definition as the members before it export it. It is in the member's schema and reserved names like any table, but it is not a layer, so once the definition closes it is pushed onto the stack without it:

```mermaid
graph LR
    rec(["member 2: … FROM t"]) -->|"reads, provisionally"| t(["t: member 1's result"])
    rec -->|"written over"| a(["the stack below t"])
    m1(["member 1"]) -->|"written over"| a

    classDef plain fill:#4a5160,stroke:#2f343f,color:#ffffff
    classDef accent fill:#2f6fb5,stroke:#1b4670,color:#ffffff
    class m1,t,a plain
    class rec accent
```

A member may read the definition when it follows a `UNION` or `UNION ALL` inside a definition of a `WITH RECURSIVE` statement. It has to stay what both SQLite and PostgreSQL accept as a recursive term: no aggregate, window or `DISTINCT`, no grouping or sorting, inner joins only, the definition placed at most once and, once it is placed, no further set operator.

#### 6.13 Subqueries: a call stack of virtual tables

A subquery is a virtual table like any other, written inside another one while that one waits. Besides the stack of closed layers (6.7) the context keeps a second, shorter stack: the **calls**, the queries suspended while a subquery inside them is written, innermost last. Each call remembers where the grammar resumes once the subquery closes and what the query around it does with the result. One subquery grammar, built once, serves every place a subquery may stand:

```mermaid
graph LR
    main(["main query: WHERE …"]) -->|"suspended in"| call1(["call: resume after ), record the condition"])
    call1 -->|"while writing"| sub(["subquery: SELECT …"])
    sub -->|") closes it"| main

    classDef plain fill:#4a5160,stroke:#2f343f,color:#ffffff
    classDef accent fill:#2f6fb5,stroke:#1b4670,color:#ffffff
    class main,call1 plain
    class sub accent
```

Where a subquery stands decides what it has to produce, its **purpose**, which becomes its contract the same way a definition's frame does:

| purpose | must produce |
|---|---|
| a value, `x = (…)` | one column of `x`'s class and one row: every item aggregates, nothing is grouped |
| the list of an `IN` | one column of the left side's class |
| an `EXISTS` | anything |
| a derived table, `(…) AS d` | every column the projection read off `d`, of the class it was read as, and no name the projection uses bare |

A value has to fold the whole query into one row, so it can only be of a class an aggregate produces: numeric, text or temporal. A boolean, binary or unknown value is never compared with a subquery.

A derived table is the hard case, because the projection names `d.user_id` before anything says what `d` is. Wherever a derived table may still be opened an alias may turn out to be one, so every column some table has stays on offer to it, and the derived table that later stands in for it is written under a contract listing exactly what was read. In the placement search of 6.10 it is one more candidate, and one that never clashes, since it supplies no bare column.

A subquery inside a condition reads the columns that are typed around it: the relation of a WHERE, the grouped columns of a HAVING, and whatever the queries around those expose in turn. It reads them qualified only, and never under a name its own FROM clause shadows. A subquery in the projection or in the FROM clause reads nothing around it: the projection is written before there is anything to read, and a derived table has no `LATERAL` to read its neighbours with. Subqueries nest two deep, and at that depth neither a subquery nor a bracket that could only open one is offered.

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

The AGPL-3.0 is a strong copyleft license that requires you to release the source code of any modified versions of this software, including when used over a network.
