# 8th - Namespace resolution

Selecting fields from tables and dynamically restricting field space as the selection goes by, then enforcing tables that satisfy the previous field selections. Supporting both a global namespace and many individual "alias" namespaces. Using boolean algebra under the hood.

Written in Rust with the `boolean_expression` crate. Two resolver types sit behind a unified `Context`:

- **`ManyResolver`** (global namespace) - builds a BDD over table variables. For each field it constructs the *exactly-one* constraint: the BDD function that is true when exactly one of the field's tables is on. Selecting a field ANDs its constraint into a running product; a field is offered only when its constraint ANDed with the current product is still satisfiable. Table resolution uses `restrict` (substituting a variable to `true`) and satisfaction checks evaluate the BDD with all variables `false`.

- **`OneResolver`** (per-alias namespace) - uses plain set intersection instead of BDD algebra. An alias denotes a single table, so each field selection intersects the candidates with the field's table set. No cross-talk between aliases, no polynomial machinery needed.

`Context` keeps one `ManyResolver` for unqualified fields and an `FxHashMap` of `OneResolver`s keyed by alias name. Setting a namespace before selecting a field routes the selection to the right resolver. Required tables are the union of both halves and the query is satisfied when both the global BDD and every alias scope have been fully discharged. The whole `Context` is `Clone`, so branching is a value copy.
