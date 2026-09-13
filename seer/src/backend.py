from __future__ import annotations

from typing import Any

import kernel as kl

# A value of the algebra: the id of a node in the ring's diagram. The diagram is
# hash consed, so equal ids mean equal polynomials and `poly == 0` still means
# "is it zero"; an id is meaningless to a ring that did not issue it.
Poly = int

# An edge label, opaque to the graph - `relationships.py` owns what is in it.
Label = Any

# A boolean function over the table variables, in the ring `GF(2)[t..]`.
Algebra = kl.BooleanPolynomialRing

# An undirected multigraph over table references. Vertices come from the edges
# alone, so a table no foreign key touches is simply not in the graph.
JoinGraph = kl.Multigraph
