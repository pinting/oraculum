# Oraculum — SQL State Machine (Experiment 9)

An interactive state machine that guides a user through constructing a **grammatically and semantically correct** SQL query, restricted to the subset:

```sql
SELECT f1, f2, alias.f4 FROM t1, t4 AS alias, t2
    JOIN ... ON ...
```

At every step the system guarantees that only valid choices are presented, so the user can never produce an illegal query. Two core mathematical ideas power this:

## Phase 1 — Field Selection & Boolean Conflict Resolution

### The problem

A field name like `id` may exist in multiple tables (`users.id`, `posts.id`, `comments.id`). When the user selects `id` without a qualifier, exactly **one** of those tables must supply it. Selecting further fields narrows the set of compatible tables.

### Boolean polynomial ring over GF(2)

[`Root`](file:///home/pinting/repos/oraculum/experiments/9-advanced-modelling/root.py#L6-L131) models this with a **Boolean polynomial ring** `B = GF(2)[t₁, t₂, …, tₙ]` where each variable `tᵢ` represents a table.

For a field `f` that exists in tables `{t₁, t₂, …, tₖ}`, the constraint is the **exactly-one / mutual-exclusion** polynomial:

```
C(f) = Σᵢ tᵢ · ∏(j≠i) (1 + tⱼ)
```

Over GF(2), `(1 + tⱼ)` acts as logical NOT (since `1 ⊕ 1 = 0`), so each term says "tᵢ is ON and all others are OFF". The sum (XOR) allows exactly one.

A running product `P` (initially `1`) accumulates all selected fields:

```
P ← P · C(f)
```

If `P` becomes `0`, the selection is contradictory. The surviving variables in `P` are the tables still in play.

**Table resolution**: substituting `tᵢ = 1` into `P` simulates "this table is chosen". If the result is non-zero the table is viable; if zero it is excluded.

**Satisfaction check**: `P` evaluated with all variables set to `0` equals `1` iff every disjunction has been collapsed to a constant (all tables decided).

### Scoped (aliased) fields

When the user writes `alias.field`, a separate [`Scope`](file:///home/pinting/repos/oraculum/experiments/9-advanced-modelling/scope.py#L1-L63) is created for that alias. `Scope` uses plain **set intersection** (not the polynomial ring) because within a single alias there is no cross-talk with other aliases — it just needs to narrow down which table the alias refers to.

[`Scopes`](file:///home/pinting/repos/oraculum/experiments/9-advanced-modelling/scopes.py#L3-L65) is the registry of all alias → Scope mappings.

[`Conflicts`](file:///home/pinting/repos/oraculum/experiments/9-advanced-modelling/conflicts.py#L5-L81) is the façade that merges Root (unqualified fields) and Scopes (aliased fields) into a single interface for required/excluded table queries.

---

## Phase 2 — FROM / JOIN via Graph Traversal

### The problem

Once the required tables are known (e.g., `{a, b, e, c AS x}`), they must be connected via foreign-key joins. The user picks a starting table, then walks the FK graph joining neighbors.

### FK relationship graph

[`Relationships`](file:///home/pinting/repos/oraculum/experiments/9-advanced-modelling/relationships.py#L14-L102) builds a SageMath `Graph` where:
- **Nodes** = table names (including aliased variants like `"c x"`)
- **Edges** = foreign-key references, labeled with the `(src_table.column, dst_table.column)` pair

The graph supports **multi-edges** (a table can reference another table through multiple FKs).

### Join traversal

1. User picks a required table → becomes the **head**.
2. `get_joinable_neighbors()` returns adjacent nodes not in the excluded set.
3. `join_table(neighbor)` merges the neighbor into the head via `graph.merge_vertices()`, collapsing the two nodes. This makes the head's new neighborhood the union of both, enabling further chained joins.
4. When required tables are exhausted, the process completes.

The merge-vertex strategy is elegant: it models the SQL semantics where a JOIN makes all columns of both tables accessible, so from the graph perspective they become one super-node.

---


## Setup

SageMath needs to be installed system-wide (as it is more than just a PIP package) and based on the system-wide Python a local virtual environment needs to be created.

```bash
sudo pacman -S python python-pip sagemath
python -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running

```bash
./main.py        # Interactive TUI
./tests.py       # Automated tests
```

### Dependencies

- **SageMath** — `BooleanPolynomialRing` (GF(2) polynomial arithmetic), `Graph` (FK relationship graph)
- **SymPy** — `simplify_logic` (DNF simplification for display)
- **sqlglot** — DDL parsing
