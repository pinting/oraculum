use aho_corasick::{AhoCorasick, AhoCorasickKind};
use pyo3::prelude::*;
use numpy::{PyArray1, PyArrayMethods};
use toktrie::TokTrie;
use std::collections::HashSet;
use std::sync::Arc;

mod number;
mod dfa;
mod index;
mod vocabulary;

use crate::dfa::fasthashdfa::FastHashDFA;
use crate::index::lattice::Lattice;
use crate::index::index::Index;
use crate::index::expression::Expression;
use crate::vocabulary::Vocabulary;
use crate::number::Number;

#[pymodule]
fn fastlines(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyVocabulary>()?;
    m.add_class::<PyAhoCorasick>()?;
    m.add_class::<PyLattice>()?;
    m.add_class::<PyTokTrie>()?;
    m.add_class::<PyExpression>()?;
    
    Ok(())
}

#[pyclass(name = "Vocabulary")]
#[derive(Clone)]
struct PyVocabulary {
    inner: Arc<Vocabulary<u32>>,
}

#[pymethods]
impl PyVocabulary {
    #[new]
    fn new(data: &[u8], eos_id: u32) -> PyResult<Self> {
        let vocabulary = Vocabulary::new(data, eos_id)
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create vocabulary"))?;

        Ok(PyVocabulary { inner: Arc::new(vocabulary) })
    }

    fn get_token_by_id(&self, id: u32) -> Option<String> {
        self.inner.get_token_by_id(id).map(|s| s.to_string())
    }

    fn get_id_by_token(&self, token: &str) -> Option<u32> {
        self.inner.get_id_by_token(token)
    }

    fn get_eos_id(&self) -> u32 {
        self.inner.get_eos_id()
    }
}

#[pyclass(name = "AhoCorasick")]
#[derive(Clone)]
struct PyAhoCorasick {
    inner: Arc<AhoCorasick>,
}

#[pymethods]
impl PyAhoCorasick {
    #[staticmethod]
    fn new(vocabulary_py: &PyVocabulary, kind: u8) -> PyResult<Self> {
        let kind = match kind {
            0 => AhoCorasickKind::ContiguousNFA,
            1 => AhoCorasickKind::NoncontiguousNFA,
            2 => AhoCorasickKind::DFA,
            _ => AhoCorasickKind::ContiguousNFA,
        };
        
        let ac = Lattice::<u16, u32>::base(kind, vocabulary_py.inner.clone())
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to build AhoCorasick base"))?;
        
        Ok(PyAhoCorasick { inner: Arc::new(ac) })
    }
}

#[pyclass(name = "Lattice")]
#[derive(Clone)]
struct PyLattice {
    inner: Arc<Lattice<u16, u32>>,
    vocabulary: Arc<Vocabulary<u32>>,
}

#[pymethods]
impl PyLattice {
    #[new]
    fn new(input: &str, vocabulary_py: &PyVocabulary, ac_base: &PyAhoCorasick) -> Self {
        let lattice = Lattice::new(input, vocabulary_py.inner.clone(), &ac_base.inner);

        PyLattice {
            inner: Arc::new(lattice),
            vocabulary: vocabulary_py.inner.clone(),
        }
    }

    fn start(&self) -> u32 {
        self.inner.start() as u32
    }

    fn transitions<'py>(&self, py: Python<'py>, node_id: u32) -> PyResult<Bound<'py, PyArray1<u32>>> {
        let t = self.inner.transitions(node_id as u16);
        let v: Vec<u32> = match t {
            Some(transitions_vec) => transitions_vec.iter().cloned().collect(),
            None => Vec::new(),
        };

        Ok(PyArray1::from_vec_bound(py, v))
    }

    fn next(&self, node_id: u32, token_id: u32) -> Option<u32> {
        self.inner.next(node_id as u16, token_id).map(|x| x as u32)
    }
}

#[pyclass(name = "TokTrie")]
#[derive(Clone)]
struct PyTokTrie {
    inner: Arc<TokTrie>,
}

#[pymethods]
impl PyTokTrie {
    #[staticmethod]
    fn new(vocabulary_py: &PyVocabulary) -> PyResult<Self> {
        let trie = Expression::<u16, u32, FastHashDFA<u16, u32, u32>>::base(vocabulary_py.inner.clone())
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to build TokTrie base"))?;
        
        Ok(PyTokTrie { inner: Arc::new(trie) })
    }
}

#[pyclass(name = "Expression")]
#[derive(Clone)]
struct PyExpression {
    inner: Arc<Expression<u16, u32, FastHashDFA<u16, u32, u32>>>,
    vocabulary: Arc<Vocabulary<u32>>,
}

#[pymethods]
impl PyExpression {
    #[new]
    fn new(input: &str, vocabulary_py: &PyVocabulary, toktrie_base: &PyTokTrie) -> PyResult<Self> {
        let expression = Expression::new(input, vocabulary_py.inner.clone(), &toktrie_base.inner)
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to create Expression index with data '{}'", input)))?;
        
        Ok(PyExpression {
            inner: Arc::new(expression),
            vocabulary: vocabulary_py.inner.clone(),
        })
    }

    fn start(&self) -> u32 {
        self.inner.start() as u32
    }

    fn transitions<'py>(&self, py: Python<'py>, node_id: u32) -> PyResult<Bound<'py, PyArray1<u32>>> {
        let t = self.inner.transitions(node_id as u16);
        let v: Vec<u32> = match t {
            Some(transitions_vec) => transitions_vec.iter().cloned().collect(),
            None => Vec::new(),
        };

        Ok(PyArray1::from_vec_bound(py, v))
    }

    fn next(&self, node_id: u32, token_id: u32) -> Option<u32> {
        self.inner.next(node_id as u16, token_id).map(|x| x as u32)
    }
}