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

pub const FAST_HASH_DFA: u8 = 0;
pub const DOUBLE_HASH_DFA: u8 = 1;
pub const FLAT_DFA: u8 = 2;

pub const AC_CONTIGUOUS_NFA: u8 = 0;
pub const AC_NONCONTIGUOUS_NFA: u8 = 1;
pub const AC_DFA: u8 = 2;

#[cfg(feature = "pyo3")]
#[pymodule]
fn fastlines(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("FAST_HASH_DFA", FAST_HASH_DFA)?;
    m.add("DOUBLE_HASH_DFA", DOUBLE_HASH_DFA)?;
    m.add("FLAT_DFA", FLAT_DFA)?;

    m.add("AC_CONTIGUOUS_NFA", AC_CONTIGUOUS_NFA)?;
    m.add("AC_NONCONTIGUOUS_NFA", AC_NONCONTIGUOUS_NFA)?;
    m.add("AC_DFA", AC_DFA)?;

    m.add_class::<PyVocabulary>()?;
    m.add_class::<PyAhoCorasick>()?;
    m.add_class::<PyLattice>()?;
    m.add_class::<PyTokTrie>()?;
    m.add_class::<PyExpression>()?;

    Ok(())
}
