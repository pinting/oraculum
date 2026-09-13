"""The two modelling primitives, which are the kernel's.

`root.py` needs a boolean algebra over table variables and `relationships.py`
needs a multigraph. Both were SageMath originally - `BooleanPolynomialRing` and
`Graph` - which was right about the mathematics and wrong about everything
else: SageMath installs system-wide only, so the build had to go hunting for an
interpreter that could see it, and it does not cross compile at all, so the
browser could never have it. Both now live in `kernel`, which seer already
depends on for its indexes and which builds for Pyodide, so this module is one
import and two names.

**The algebra** is a port of what SageMath does rather than an alternative to
it. `BooleanPolynomialRing` is PolyBoRi, and PolyBoRi holds a boolean
polynomial as a zero-suppressed decision diagram: a polynomial over
`GF(2)[t..]/(t^2 - t)` is a sum of squarefree monomials and nothing else, so it
is a set of subsets of the variables, and a ZDD is the canonical way to hold
one of those. `kernel/src/algebra` is that diagram without CUDD underneath it,
and its multiply follows PolyBoRi's `dd_multiply` down to the rearrangement
that gets a product's three cross terms out of two recursive calls.

What the diagram buys is what it buys PolyBoRi. The constraint a field name
contributes is "exactly one of the `k` tables it lives in", whose normal form
has `2^(k-1)` monomials - and `id` lives in every table there is. The ZDD for
that polynomial is two nodes per level.

**The graph** is a multigraph whose only mutation is vertex contraction, which
is the only mutation join resolution performs. The point of saying so is
`copy()`: every branch of the syntax graph wants its own graph and most
branches are thrown away unexamined, so the edges live in a shared immutable
base and the whole of the mutable state is one array saying which vertex each
vertex has been folded into. A copy is two reference count bumps and a branch
that joins nothing allocates nothing.

Both are used as the extension exposes them, with no wrapper in between - the
Rust already spells the methods the way this side wants them, and a forwarding
class would only add a Python frame to every call on the hot path.

`tests/model.py` is what keeps them honest: both are checked against a brute
force reference written in the test, which is the only independent evidence
there is now that the ports are the objects they claim to be.
"""

from __future__ import annotations

from typing import Any

import kernel as kl

# A value of the algebra: the id of a node in the ring's diagram.
#
# A polynomial is a value - it is copied into every branch of the syntax graph
# and compared for equality constantly - and an `int` is the cheapest value
# Python has. The diagram is hash consed, so equal ids mean equal polynomials
# and `poly == 0` still means "is it zero". An id is meaningless to a ring that
# did not issue it, which is harmless: a `Root` holds its ring for as long as
# it holds any.
Poly = int

# An edge label. Opaque to the graph, which only ever stores it and hands it
# back - `relationships.py` owns what is in it.
Label = Any

# A boolean function over the table variables, in the ring `GF(2)[t..]`.
Algebra = kl.BooleanPolynomialRing

# An undirected multigraph over table references. Vertices come from the edges
# alone - a table no foreign key touches is simply not in the graph, and
# `__contains__` says so.
JoinGraph = kl.Multigraph
