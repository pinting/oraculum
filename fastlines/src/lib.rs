#[cfg(feature = "pyo3")]
use pyo3::prelude::*;

#[cfg(feature = "pyo3")]
use pyo3::types::PyModule;

mod number;
mod dfa;
mod index;
mod vocabulary;

#[cfg(feature = "pyo3")]
pub mod pyvocabulary;

pub use crate::number::Number;
pub use crate::dfa::dfa::DFA;
pub use crate::dfa::fasthashdfa::FastHashDFA;
pub use crate::dfa::doublehashdfa::DoubleHashDFA;
pub use crate::dfa::flatdfa::FlatDFA;
pub use crate::index::index::Accepting;
pub use crate::index::index::BaseIndex;
pub use crate::index::index::Index;
pub use crate::index::lattice::Lattice;
pub use crate::index::expression::Expression;
pub use crate::vocabulary::Vocabulary;

#[cfg(feature = "pyo3")]
use crate::pyvocabulary::PyVocabulary;
#[cfg(feature = "pyo3")]
use crate::index::pylattice::{PyAhoCorasick, PyLattice};
#[cfg(feature = "pyo3")]
use crate::index::pyexpression::{PyExpression, PyTokTrie};

#[cfg(feature = "pyo3")]
#[pymodule]
fn fastlines(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyVocabulary>()?;
    m.add_class::<PyAhoCorasick>()?;
    m.add_class::<PyLattice>()?;
    m.add_class::<PyTokTrie>()?;
    m.add_class::<PyExpression>()?;

    Ok(())
}
