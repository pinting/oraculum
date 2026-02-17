use aho_corasick::{AhoCorasick, AhoCorasickKind};
use pyo3::prelude::*;
use pyo3::types::{PyType, PyModule};
use numpy::{PyArray1, PyArrayMethods};
use toktrie::TokTrie;
use std::collections::HashSet;
use std::sync::Arc;
use std::borrow::Cow;

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

    #[classmethod]
    fn from_file_path(_cls: &Bound<'_, PyType>, _py: Python<'_>, file_path: &str, eos_id: u32) -> PyResult<Self> {
        let vocabulary = Vocabulary::from_file_path(file_path, eos_id)
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create vocabulary from file"))?;
        
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
            Some(tv) => tv.iter().cloned().collect(),
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
    dfa_type: u8,
    n_size: u8,
    t_size: u8,
    o_size: u8,
}

#[pymethods]
impl PyTokTrie {
    #[staticmethod]
    fn new(vocabulary_py: &PyVocabulary, dfa_type: u8, n_size: u8, t_size: u8, o_size: u8) -> PyResult<Self> {
        let trie = Expression::<u16, u32, FastHashDFA<u16, u32, u32>>::base(vocabulary_py.inner.clone())
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to build TokTrie base"))?;
        
        Ok(PyTokTrie { 
            inner: Arc::new(trie),
            dfa_type,
            n_size,
            t_size,
            o_size,
        })
    }
}

#[derive(Clone)]
enum ExpressionVariant {
    // FastHashDFA (Type 0)
    // Format: FH_<N_SIZE>_<T_SIZE>_<O_SIZE>
    FhU16U32U32(Arc<Expression<u16, u32, FastHashDFA<u16, u32, u32>>>),
    FhU16U32U16(Arc<Expression<u16, u32, FastHashDFA<u16, u32, u16>>>),
    FhU32U32U32(Arc<Expression<u32, u32, FastHashDFA<u32, u32, u32>>>),
    FhU32U32U16(Arc<Expression<u32, u32, FastHashDFA<u32, u32, u16>>>),
}

impl ExpressionVariant {
    fn start(&self) -> u32 {
        match self {
            Self::FhU16U32U32(e) => e.start() as u32,
            Self::FhU16U32U16(e) => e.start() as u32,
            Self::FhU32U32U32(e) => e.start(),
            Self::FhU32U32U16(e) => e.start(),
        }
    }

    fn next(&self, node_id: u32, token_id: u32) -> Option<u32> {
        match self {
            Self::FhU16U32U32(e) => e.next(node_id as u16, token_id).map(|x| x as u32),
            Self::FhU16U32U16(e) => e.next(node_id as u16, token_id).map(|x| x as u32),
            Self::FhU32U32U32(e) => e.next(node_id, token_id),
            Self::FhU32U32U16(e) => e.next(node_id, token_id),
        }
    }

    fn transitions<'a>(&'a self, node_id: u32) -> Option<Cow<'a, [u32]>> {
        match self {
            Self::FhU16U32U32(e) => e.transitions(node_id as u16),
            Self::FhU16U32U16(e) => e.transitions(node_id as u16),
            Self::FhU32U32U32(e) => e.transitions(node_id),
            Self::FhU32U32U16(e) => e.transitions(node_id),
        }
    }
}

#[pyclass(name = "Expression")]
#[derive(Clone)]
struct PyExpression {
    inner: ExpressionVariant,
    vocabulary: Arc<Vocabulary<u32>>,
}

#[pymethods]
impl PyExpression {
    #[new]
    fn new(input: &str, vocabulary_py: &PyVocabulary, toktrie_base: &PyTokTrie) -> PyResult<Self> {
        // Unpack configuration from the trie
        let dfa_type = toktrie_base.dfa_type;
        let n_size = toktrie_base.n_size;
        let t_size = toktrie_base.t_size;
        let o_size = toktrie_base.o_size;

        if t_size != 4 {
             return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("Vocabulary is u32, so token size (T) must be 4."));
        }

        let variant = match (dfa_type, n_size, o_size) {
            (0, 2, 4) => {
                let e = Expression::<u16, u32, FastHashDFA<u16, u32, u32>>::new(
                    input, vocabulary_py.inner.clone(), &toktrie_base.inner
                ).ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Expression"))?;

                ExpressionVariant::FhU16U32U32(Arc::new(e))
            },

            (0, 2, 2) => {
                let e = Expression::<u16, u32, FastHashDFA<u16, u32, u16>>::new(
                    input, vocabulary_py.inner.clone(), &toktrie_base.inner
                ).ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Expression"))?;

                ExpressionVariant::FhU16U32U16(Arc::new(e))
            },

            (0, 4, 4) => {
                let e = Expression::<u32, u32, FastHashDFA<u32, u32, u32>>::new(
                    input, vocabulary_py.inner.clone(), &toktrie_base.inner
                ).ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Expression"))?;

                ExpressionVariant::FhU32U32U32(Arc::new(e))
            },

            (0, 4, 2) => {
                let e = Expression::<u32, u32, FastHashDFA<u32, u32, u16>>::new(
                    input, vocabulary_py.inner.clone(), &toktrie_base.inner
                ).ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Expression"))?;

                ExpressionVariant::FhU32U32U16(Arc::new(e))
            },
            
            _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Unsupported configuration: Type={}, N={}, T={}, O={}", dfa_type, n_size, t_size, o_size)
            )),
        };
        
        Ok(PyExpression {
            inner: variant,
            vocabulary: vocabulary_py.inner.clone(),
        })
    }

    fn start(&self) -> u32 {
        self.inner.start()
    }

    fn transitions<'py>(&self, py: Python<'py>, node_id: u32) -> PyResult<Bound<'py, PyArray1<u32>>> {
        let t = self.inner.transitions(node_id);
        let v: Vec<u32> = match t {
            Some(tv) => tv.iter().cloned().collect(),
            None => Vec::new(),
        };

        Ok(PyArray1::from_vec_bound(py, v))
    }

    fn next(&self, node_id: u32, token_id: u32) -> Option<u32> {
        self.inner.next(node_id, token_id)
    }
}