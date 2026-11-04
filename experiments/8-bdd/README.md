# 8th - Namespace resolution

This experiment selects fields from tables and dynamically restricts available fields during selection, enforcing tables that satisfy earlier choices. It supports both a global namespace and individual alias namespaces using boolean algebra.

Written in Rust with the `boolean_expression` crate, two resolver types sit behind a unified `Context`:

- `ManyResolver` (global namespace): builds a BDD over table variables. For each field, it constructs the *exactly-one* constraint: the BDD function that evaluates to true when exactly one of the field's tables is active. Selecting a field ANDs its constraint into a running product; a field is offered only when its constraint ANDed with the current product remains satisfiable. Table resolution uses `restrict` (substituting a variable to `true`), and satisfaction checks evaluate the BDD with all variables set to `false`.

- `OneResolver` (per-alias namespace): uses set intersection instead of BDD algebra. An alias denotes a single table, so each field selection intersects candidate tables with the field's table set. This avoids polynomial overhead because aliases do not cross-reference each other.

`Context` maintains one `ManyResolver` for unqualified fields and an `FxHashMap` of `OneResolver` instances keyed by alias name. Setting a namespace before selecting a field routes the selection to the corresponding resolver. Required tables form the union of both resolvers, and a query is satisfied when both the global BDD and every alias scope have been discharged. `Context` implements `Clone`, allowing branching via value copies.
