//! `Expression` and its TokTrie base, exposed to Python.
//!
//! For callers that want to own an index outright and walk it themselves, node
//! id in hand. `Factory` is the other way round, where the index stays in the
//! kernel and only its id comes back.
//!
//! The base is its own class because it is the expensive half and is shared by
//! every expression built from it.

use pyo3::prelude::*;
use numpy::{PyArray1, PyArrayMethods};
use toktrie::TokTrie;
use std::sync::Arc;

use crate::pyvocabulary::PyVocabulary;
use crate::dfa::flatdfa::FlatDFA;
use crate::index::index::{Index, BaseIndex, Accepting};
use crate::index::expression::Expression;
use crate::number::Number;

type N = u32;
type T = u32;
type D = FlatDFA<N, T>;

#[pyclass(name = "TokTrie")]
#[derive(Clone)]
pub struct PyTokTrie {
    pub unit: Arc<TokTrie>,
}

#[pymethods]
impl PyTokTrie {
    #[staticmethod]
    fn new(py: Python<'_>, vocabulary_py: &PyVocabulary) -> PyResult<Self> {
        let vocabulary = vocabulary_py.unit.clone();

        // Building the base scans the whole vocabulary, so let other Python
        // threads run while it happens.
        let trie = py.allow_threads(move || Expression::<N, T, D>::base(vocabulary))
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to build TokTrie base"))?;

        Ok(PyTokTrie { unit: Arc::new(trie) })
    }
}

#[pyclass(name = "Expression")]
#[derive(Clone)]
pub struct PyExpression {
    unit: Arc<Expression<N, T, D>>,
}

#[pymethods]
impl PyExpression {
    #[new]
    fn new(py: Python<'_>, input: &str, vocabulary_py: &PyVocabulary, toktrie_base: &PyTokTrie) -> PyResult<Self> {
        let input = input.to_string();
        let vocabulary = vocabulary_py.unit.clone();
        let toktrie_base = toktrie_base.unit.clone();

        // Index construction touches no Python state, so the GIL is released
        // for its duration and callers may build indexes in parallel.
        let e = py.allow_threads(move || Expression::<N, T, D>::new(&input, vocabulary, &toktrie_base))
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Expression"))?;

        Ok(PyExpression { unit: Arc::new(e) })
    }

    fn node_count(&self) -> u64 {
        self.unit.node_count().to_usize() as u64
    }

    fn transitions<'py>(&self, py: Python<'py>, node_id: u64) -> PyResult<Bound<'py, PyArray1<u64>>> {
        let n = N::from_usize(node_id as usize);

        let v: Vec<u64> = match self.unit.transitions(n) {
            Some(c) => c.iter().map(|x| x.to_usize() as u64).collect(),
            None => Vec::new(),
        };

        Ok(PyArray1::from_vec_bound(py, v))
    }

    fn next(&self, node_id: u64, token_id: u64) -> Option<u64> {
        let n = N::from_usize(node_id as usize);
        let t = T::from_usize(token_id as usize);

        self.unit.next(n, t).map(|v| v.to_usize() as u64)
    }

    fn accepting(&self, node_id: u64) -> Option<bool> {
        let n = N::from_usize(node_id as usize);

        match self.unit.accepting(n) {
            Accepting::No => None,
            Accepting::Yes(is_more) => Some(is_more),
        }
    }

    fn memory_usage(&self) -> usize {
        self.unit.memory_usage()
    }
}
