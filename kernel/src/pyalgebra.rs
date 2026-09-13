//! `BooleanPolynomialRing`, exposed to Python.
//!
//! The surface is SageMath's, narrowed to what a mutual exclusion model asks
//! for, so that the module drops in where `sage.all.BooleanPolynomialRing` was
//! without a translation layer. The one difference is what a polynomial is on
//! this side of the boundary: SageMath hands back an object, and this hands
//! back the `int` id of a node in the ring's diagram.
//!
//! That is deliberate. A polynomial is a value - it is copied into every branch
//! of a syntax graph and compared for equality constantly - and an `int` is the
//! cheapest value Python has. Equality of ids *is* equality of polynomials,
//! because the diagram is hash consed, so `poly == 0` still means "zero".
//!
//! Ids are only meaningful to the ring that issued them. Every caller holds its
//! ring for as long as it holds an id, which `root.py` does by construction.
//!
//! `nonzero` and `viable` have no SageMath counterpart. They are the two loops
//! `root.py` runs after every selection - one over the field constraints, one
//! over the table variables - moved across the boundary so that a refresh costs
//! one call rather than two per field.

use pyo3::exceptions::PyKeyError;
use pyo3::prelude::*;
use pyo3::types::PyFrozenSet;

use crate::algebra::ring::Ring;
use crate::algebra::zdd::NodeId;

#[pyclass(name = "BooleanPolynomialRing")]
pub struct PyRing {
    ring: Ring,
}

#[pymethods]
impl PyRing {
    /// The ring over these variables, in this order.
    #[new]
    fn new(names: Vec<String>) -> Self {
        Self {
            ring: Ring::new(names),
        }
    }

    /// The constant `1` - the function nothing has constrained yet.
    fn one(&self) -> NodeId {
        self.ring.one()
    }

    /// The constant `0` - the function nothing satisfies.
    fn zero(&self) -> NodeId {
        self.ring.zero()
    }

    /// `SUM_i t_i * PRODUCT_(j != i) (1 + t_j)` - exactly one of `names` is on.
    fn mutual_exclusion(&mut self, names: Vec<String>) -> PyResult<NodeId> {
        self.ring
            .mutual_exclusion(&names)
            .ok_or_else(|| PyKeyError::new_err(format!("not a variable of the ring: {names:?}")))
    }

    /// Conjunction. Both operands are `0/1` valued, so the product is `AND`.
    fn product(&mut self, left: NodeId, right: NodeId) -> NodeId {
        self.ring.product(left, right)
    }

    /// Addition over GF(2), which is `XOR`.
    fn sum(&mut self, left: NodeId, right: NodeId) -> NodeId {
        self.ring.sum(left, right)
    }

    fn is_zero(&self, poly: NodeId) -> bool {
        self.ring.is_zero(poly)
    }

    /// Substitute `name = 1` - assert the table is in the FROM clause.
    fn assume(&mut self, poly: NodeId, name: &str) -> NodeId {
        self.ring.assume(poly, name)
    }

    /// The variables the polynomial actually depends on.
    fn constrained<'py>(&self, py: Python<'py>, poly: NodeId) -> PyResult<Bound<'py, PyFrozenSet>> {
        PyFrozenSet::new(py, self.ring.constrained(poly))
    }

    /// Whether the all-zero assignment satisfies it, i.e. it is settled.
    fn holds_empty(&self, poly: NodeId) -> bool {
        self.ring.holds_empty(poly)
    }

    /// Which of `others` have a non-zero product with `poly`, in order.
    fn nonzero(&mut self, poly: NodeId, others: Vec<NodeId>) -> Vec<bool> {
        self.ring.nonzero(poly, &others)
    }

    /// The variables that can still be asserted without collapsing `poly`.
    fn viable<'py>(&mut self, py: Python<'py>, poly: NodeId) -> PyResult<Bound<'py, PyFrozenSet>> {
        let flags: Vec<bool> = self.ring.viable(poly);
        let names: Vec<&str> = self
            .ring
            .variables()
            .iter()
            .zip(&flags)
            .filter(|&(_, &viable)| viable)
            .map(|(name, _)| name.as_str())
            .collect();

        PyFrozenSet::new(py, names)
    }

    /// Disjunctive normal form. Debug output only.
    fn render(&mut self, poly: NodeId) -> String {
        self.ring.render(poly)
    }

    /// How many monomials the polynomial has - what listing them would cost.
    fn term_count(&self, poly: NodeId) -> u128 {
        self.ring.terms(poly)
    }

    /// Diagram nodes in the whole ring, terminals included.
    fn node_count(&self) -> usize {
        self.ring.node_count()
    }

    fn memory_usage(&self) -> usize {
        self.ring.memory_usage()
    }

    fn __repr__(&self) -> String {
        format!(
            "BooleanPolynomialRing({} variables, {} nodes)",
            self.ring.variables().len(),
            self.ring.node_count()
        )
    }
}
