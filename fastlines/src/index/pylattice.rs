use aho_corasick::{AhoCorasick, AhoCorasickKind};
use pyo3::prelude::*;
use numpy::{PyArray1, PyArrayMethods};
use std::sync::Arc;

use crate::pyvocabulary::PyVocabulary;
use crate::index::lattice::Lattice;
use crate::index::index::{Index, BaseIndex, Accepting};

type N = u32;
type T = u32;

const AC_KIND: AhoCorasickKind = AhoCorasickKind::ContiguousNFA;

#[pyclass(name = "AhoCorasick")]
#[derive(Clone)]
pub struct PyAhoCorasick {
    pub unit: Arc<AhoCorasick>,
}

#[pymethods]
impl PyAhoCorasick {
    #[staticmethod]
    fn new(vocabulary_py: &PyVocabulary) -> PyResult<Self> {
        let ac = Lattice::<N, T>::base(AC_KIND, vocabulary_py.unit.clone())
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to build AhoCorasick base"))?;

        Ok(PyAhoCorasick { unit: Arc::new(ac) })
    }
}

#[pyclass(name = "Lattice")]
#[derive(Clone)]
pub struct PyLattice {
    unit: Arc<Lattice<N, T>>,
}

#[pymethods]
impl PyLattice {
    #[new]
    fn new(input: &str, vocabulary_py: &PyVocabulary, ac_base: &PyAhoCorasick) -> PyResult<Self> {
        let lattice = Lattice::<N, T>::new(input, vocabulary_py.unit.clone(), &ac_base.unit)
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Lattice"))?;

        Ok(PyLattice { unit: Arc::new(lattice) })
    }

    fn node_count(&self) -> u64 {
        self.unit.node_count() as u64
    }

    fn transitions<'py>(&self, py: Python<'py>, node_id: u64) -> PyResult<Bound<'py, PyArray1<u64>>> {
        let v: Vec<u64> = self.unit.transitions(node_id as N)
            .map_or(Vec::new(), |c| c.iter().map(|&x| x as u64).collect());

        Ok(PyArray1::from_vec_bound(py, v))
    }

    fn next(&self, node_id: u64, token_id: u64) -> Option<u64> {
        self.unit.next(node_id as N, token_id as T).map(|n| n as u64)
    }

    fn accepting(&self, node_id: u64) -> Option<bool> {
        match self.unit.accepting(node_id as N) {
            Accepting::No => None,
            Accepting::Yes(is_more) => Some(is_more),
        }
    }

    fn memory_usage(&self) -> usize {
        self.unit.memory_usage()
    }
}
