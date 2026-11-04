# 9th - Namespace and table relation resolution

This experiment extends `Context` in Python using SageMath to add schema parsing, a GF(2) polynomial ring, and foreign-key graph traversal. `seer` adopts this approach.

### Field selection and boolean conflict resolution

`Root` replaces the BDD of Experiment 8 with a `BooleanPolynomialRing` over GF(2). For each field, the *exactly-one* constraint is built as the sum of terms $t_i \cdot \prod_{j \neq i}(1 + t_j)$, which over GF(2) is `1` when exactly one table is on. Selecting a field multiplies its constraint into a running product $P$. Table viability is tested by substituting $t = 1$, and satisfaction checks evaluate $P$ with all variables set to `0`. `Scope` handles aliased fields with set intersection (as `OneResolver` did), `Scopes` is the registry, and `Conflicts` is the façade unifying both. It propagates alias table resolutions back into `Root` when an aliased table also appears in the global polynomial.

### FROM and JOIN through graph contraction

`Relationships` builds a SageMath `Graph` whose nodes are the required tables (including aliased variants like `"c x"`) and whose edges are foreign-key references, each labelled with the `(src_table.column, dst_table.column)` pair. Growing a FROM entry is a sequence of vertex contractions (`merge_vertices`): joining a neighbour merges it into the head, unifying both neighbourhoods so that tables two hops away become directly reachable. The `ON` columns are read from the edge label directly. Excluded tables (those ruled out by the conflict resolver) are hidden from the joinable set.
