//! kernel - token indexes, and the machinery for walking many of them at once.
//!
//! An *index* is a language over vocabulary tokens. A `Lattice` spells one
//! constant string, an `Expression` a regular expression, and a `Group` is one
//! index minus any number of others. All three are immutable and hold no
//! position of their own, which is what lets a single index back every walk
//! that needs it.
//!
//! The walking is `runtime`. A `Factory` builds indexes and answers with ids,
//! a `Memory` is one walk over one index, a `Head` pairs a walk with whatever
//! the caller attached to it, and a `Runner` advances every head over each
//! token across a worker pool. When a head reaches the end of its index the
//! caller's `Resolver` is asked what may follow.
//!
//! That last question is the whole interface to the language being generated:
//! the crate builds no grammar and never looks inside a payload. The `pyo3`
//! feature adds the Python bindings, which fix the node and token widths and
//! the transition layout - see `pyfactory`.
//!
//! Alongside the indexes sit the two structures the *caller's* model is built
//! out of, which have nothing to do with tokens and everything to do with being
//! copied a great many times per generated statement:
//!
//! * `algebra` - boolean polynomials over `GF(2)` as zero-suppressed decision
//!   diagrams, which is how SageMath's `BooleanPolynomialRing` holds one;
//! * `graph` - an undirected multigraph whose only mutation is contraction, so
//!   that a copy of it costs two reference count bumps.

#[cfg(feature = "pyo3")]
use pyo3::prelude::*;

#[cfg(feature = "pyo3")]
use pyo3::types::PyModule;

mod number;
mod algebra;
mod dfa;
mod graph;
mod index;
mod runtime;
mod vocabulary;

#[cfg(feature = "pyo3")]
pub mod pyalgebra;

#[cfg(feature = "pyo3")]
pub mod pygraph;

#[cfg(feature = "pyo3")]
pub mod pyvocabulary;

#[cfg(feature = "pyo3")]
pub mod pyfactory;

#[cfg(feature = "pyo3")]
pub mod pyrunner;

pub use crate::number::Number;
pub use crate::algebra::ring::Ring;
pub use crate::algebra::zdd::{NodeId, VarId, Zdd};
pub use crate::graph::multigraph::Multigraph;
pub use crate::dfa::dfa::DFA;
pub use crate::dfa::fasthashdfa::FastHashDFA;
pub use crate::dfa::doublehashdfa::DoubleHashDFA;
pub use crate::dfa::flatdfa::FlatDFA;
pub use crate::index::index::Accepting;
pub use crate::index::index::BaseIndex;
pub use crate::index::index::Index;
pub use crate::index::group::Group;
pub use crate::index::unit::Unit;
pub use crate::index::lattice::Lattice;
pub use crate::index::expression::Expression;
pub use crate::runtime::factory::{Draft, Factory, IndexId};
pub use crate::runtime::head::{Head, HeadId};
pub use crate::runtime::memory::Memory;
pub use crate::runtime::resolver::{Expansion, Report, Request, Resolver, Terminal};
pub use crate::runtime::runner::Runner;
pub use crate::vocabulary::Vocabulary;

#[cfg(feature = "pyo3")]
use crate::pyvocabulary::PyVocabulary;
#[cfg(feature = "pyo3")]
use crate::index::pylattice::{PyAhoCorasick, PyLattice};
#[cfg(feature = "pyo3")]
use crate::index::pyexpression::{PyExpression, PyTokTrie};
#[cfg(feature = "pyo3")]
use crate::pyalgebra::PyRing;
#[cfg(feature = "pyo3")]
use crate::pygraph::PyMultigraph;
#[cfg(feature = "pyo3")]
use crate::pyfactory::PyFactory;
#[cfg(feature = "pyo3")]
use crate::pyrunner::{PyHead, PyRunner};

#[cfg(feature = "pyo3")]
#[pymodule]
fn kernel(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyVocabulary>()?;
    m.add_class::<PyAhoCorasick>()?;
    m.add_class::<PyLattice>()?;
    m.add_class::<PyTokTrie>()?;
    m.add_class::<PyExpression>()?;
    m.add_class::<PyFactory>()?;
    m.add_class::<PyRunner>()?;
    m.add_class::<PyHead>()?;
    m.add_class::<PyRing>()?;
    m.add_class::<PyMultigraph>()?;

    Ok(())
}
