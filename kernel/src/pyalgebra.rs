//! `BooleanPolynomialRing`, exposed to Python.
//!
//! A polynomial crosses as the `int` id of a node in the ring's diagram. The
//! diagram is hash consed, so equality of ids is equality of polynomials and
//! `poly == 0` still means "zero"; an id means nothing to a ring that did not
//! issue it.
//!
//! `nonzero` and `viable` are the two loops `root.py` would otherwise run after
//! every selection, moved across the boundary.

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

    fn zero(&self) -> NodeId {
        self.ring.zero()
    }

    /// `SUM_i t_i * PRODUCT_(j != i) (1 + t_j)` - exactly one of `names` is on.
    fn mutual_exclusion(&mut self, names: Vec<String>) -> PyResult<NodeId> {
        self.ring
            .mutual_exclusion(&names)
            .ok_or_else(|| PyKeyError::new_err(format!("not a variable of the ring: {names:?}")))
    }

    /// Conjunction: both operands are `0/1` valued, so the product is `AND`.
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

    /// How many monomials the polynomial has.
    fn term_count(&self, poly: NodeId) -> u128 {
        self.ring.terms(poly)
    }

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
