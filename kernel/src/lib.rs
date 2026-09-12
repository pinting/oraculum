#[cfg(feature = "pyo3")]
use pyo3::prelude::*;

#[cfg(feature = "pyo3")]
use pyo3::types::PyModule;

mod number;
mod dfa;
mod index;
mod runtime;
mod vocabulary;

#[cfg(feature = "pyo3")]
pub mod pyvocabulary;

#[cfg(feature = "pyo3")]
pub mod pyfactory;

#[cfg(feature = "pyo3")]
pub mod pyrunner;

pub use crate::number::Number;
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

    Ok(())
}
