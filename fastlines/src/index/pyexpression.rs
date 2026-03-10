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
    fn new(vocabulary_py: &PyVocabulary) -> PyResult<Self> {
        let trie = Expression::<N, T, D>::base(vocabulary_py.unit.clone())
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
    fn new(input: &str, vocabulary_py: &PyVocabulary, toktrie_base: &PyTokTrie) -> PyResult<Self> {
        let e = Expression::<N, T, D>::new(input, vocabulary_py.unit.clone(), &toktrie_base.unit)
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
