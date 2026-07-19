# Draft

## 1st example

Tables, fields and relations.

users(KEY id, first_name, last_name, email)
posts(KEY id, user_id -> users.id, title, body)
comments(KEY id, user_id -> users.id, post_id -> posts.id, title, body)

### 1st layer

Selecting fields names either on the global scope or in on-the-fly defined alias scopes.

A boolean algebra based resolver should resolve the possible tables based on the incoming field names.

There should be 2 types of resolver - many resolver and one resolver.

Many resolver is solely used on the global scope where multiply tables can exist, while one resolver focuses on a single alias scope where only one table can exists (or an XOR of many possible table candidates).

`f(.) = id, first_name, last_name, email, user_id, title, body, post_id`

SELECT id

`. = users XOR posts XOR comments`
`f(.) = id, first_name, last_name, email, user_id, title, body, post_id`

> SELECT user_id

. = (users XOR posts XOR comments) AND (posts XOR comments) = (posts XOR comments) AND NOT(users)

`f(.) = id, user_id, title, body, post_id`

> SELECT foobar.title

`. = (posts XOR comments) AND NOT(users)`
`foobar = posts XOR comments`
`f(.) = id, user_id, title, body, post_id`
`f(foobar) = id, user_id, title, body, post_id`

> SELECT foobar.body

`. = (posts XOR comments) AND NOT(users)`
`foobar = posts XOR comments`
`f(.) = id, user_id, title, body, post_id`
`f(foobar) = id, user_id, title, body, post_id`

DONE

Jumping to the 2nd layer

### 2nd layer

Transform the tables to nodes and their relations to edges. Save the fields connection A to B and B to A as metadata of the edges.

Transform the boolean algebra based scopes into spanning trees or spanning forests. To reduce computational costs do not calculate all possible paths, rather let the user start at either required nodes.

E.g. this is the initial state:

`. = (posts XOR comments) AND NOT(users)`
`foobar = posts XOR comments`

The table relations transformed to the following graph:

```
users.id -> users.id
users.id -> posts.user_id
users.id -> comments.user_id

posts.id -> posts.id
posts.id -> comments.post_id

posts.user_id -> posts.user_id
posts.user_id -> users.id
posts.user_id -> comments.user_id

comments.id <-> comments.id

comments.user_id <-> comments.user_id
comments.user_id <-> posts.user_id
comments.user_id <-> users.id

comments.post_id <-> comments.post_id
comments.post_id <-> posts.id
```

A possible solution:

`n() = posts, comments, posts AS foobar, comments AS foobar`

> posts

E.g. let's say, posts it selected on the global namespace, so comments are ruled out (and users were always ruled out). The remaining variables are inside NOT operations, so the equation is solved as posts = TRUE, users = FALSE, comments = FALSE. The global scope is satisfied. The foobar alias scope remains unsatisfied. 

. = NOT(users) AND NOT(comments) = SATISFIED
foobar = posts XOR comments

In the graph everything is connected to everything, so the possible paths to resolve the remaining dependencies:

`n() = JOIN posts AS foobar, JOIN comments AS foobar, posts AS foobar, comments AS foobar`

1. Direct joined

> JOIN posts AS foobar ON posts.id = foobar.id

Does not make much sense, but it is a valid solution.

2. Direct joined

>  JOIN comments AS foobar ON posts.id = comments.post_id

3. Independent

> posts AS foobar

Does not make much sense, but it is a valid solution. Importing independently posts as foobar.

4. Independent

> comments AS foobar

Importing independently comments as foobar.

## 2nd example, analyzing more closely how to manage the graph

Let's draft the following simplified model space.

A(KEY k, bk -> B.k, f1, f2)
B(KEY k, ck -> C.k, f2, f3)
C(KEY k, dk -> D.k, ek -> E.k, f4, f5)
D(KEY k, f4, f5, f6)
E(KEY k, f4, f5, f6)

### 1st layer

> f1

`. = A`
`f(.) = k, bk, f1, f2, ck, f3, dk, ek, f4, f5, f6`

> x.f6

`. = A`
`x = D XOR E`
`f(.) = k, bk, f1, f2, ck, f3, dk, ek, f4, f5, f6`
`f(x) = k, f4, f5, f6`

> f3

`. = A AND B`
`x = D XOR E`
`f(.) = bk, f1, ck, f3, dk, ek, f4, f5, f6`
`f(x) = k, f4, f5, f6`

As both f1 and f3 are selected, A and B are definitely needed. As they do conflict on f2 and k, these fields need to be excluded.

### 2nd layer

`n() = A, D AS x, E AS x`

> D AS x

. = A
x = (D XOR E) AND D = NOT(E) AND D

The graph looks like the following

A - B - C - D
        |
        \ - E

We can continue to join nodes to satisfy A.

`n() = JOIN C, A`

> JOIN C ON D.k = C.dk

`n() = JOIN B, A`

> JOIN B ON C.k = B.ck

`n() = JOIN A, A`

> JOIN A ON B.k = A.bk

SATISFIED!