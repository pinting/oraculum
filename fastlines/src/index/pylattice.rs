use aho_corasick::{AhoCorasick, AhoCorasickKind};
use pyo3::prelude::*;
use numpy::{PyArray1, PyArrayMethods};
use std::sync::Arc;

use crate::pyvocabulary::{PyVocabulary, VocabularyUnit};
use crate::index::lattice::Lattice;
use crate::index::index::Index;

#[pyclass(name = "AhoCorasick")]
#[derive(Clone)]
pub struct PyAhoCorasick {
    pub unit: Arc<AhoCorasick>,
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

        let ac = match &vocabulary_py.unit {
            VocabularyUnit::U16(v) => Lattice::<u32, u16>::base(kind, v.clone()),
            VocabularyUnit::U32(v) => Lattice::<u32, u32>::base(kind, v.clone()),
            VocabularyUnit::U64(v) => Lattice::<u32, u64>::base(kind, v.clone()),
        }.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to build AhoCorasick base"))?;

        Ok(PyAhoCorasick { unit: Arc::new(ac) })
    }
}

#[derive(Clone)]
pub enum LatticeUnit {
    U16(Arc<Lattice<u32, u16>>),
    U32(Arc<Lattice<u32, u32>>),
    U64(Arc<Lattice<u32, u64>>),
}

#[pyclass(name = "Lattice")]
#[derive(Clone)]
pub struct PyLattice {
    unit: LatticeUnit,
}

#[pymethods]
impl PyLattice {
    #[new]
    fn new(input: &str, vocabulary_py: &PyVocabulary, ac_base: &PyAhoCorasick) -> Self {
        let unit = match &vocabulary_py.unit {
            VocabularyUnit::U16(v) => LatticeUnit::U16(Arc::new(Lattice::new(input, v.clone(), &ac_base.unit))),
            VocabularyUnit::U32(v) => LatticeUnit::U32(Arc::new(Lattice::new(input, v.clone(), &ac_base.unit))),
            VocabularyUnit::U64(v) => LatticeUnit::U64(Arc::new(Lattice::new(input, v.clone(), &ac_base.unit))),
        };

        PyLattice { unit }
    }

    fn node_count(&self) -> u64 {
        match &self.unit {
            LatticeUnit::U16(l) => l.node_count() as u64,
            LatticeUnit::U32(l) => l.node_count() as u64,
            LatticeUnit::U64(l) => l.node_count() as u64,
        }
    }

    fn transitions<'py>(&self, py: Python<'py>, node_id: u64) -> PyResult<Bound<'py, PyArray1<u64>>> {
        let v: Vec<u64> = match &self.unit {
            LatticeUnit::U16(l) => l.transitions(node_id as u32).map_or(Vec::new(), |c| c.iter().map(|&x| x as u64).collect()),
            LatticeUnit::U32(l) => l.transitions(node_id as u32).map_or(Vec::new(), |c| c.iter().map(|&x| x as u64).collect()),
            LatticeUnit::U64(l) => l.transitions(node_id as u32).map_or(Vec::new(), |c| c.iter().map(|&x| x as u64).collect()),
        };

        Ok(PyArray1::from_vec_bound(py, v))
    }

    fn next(&self, node_id: u64, token_id: u64) -> Option<u64> {
        match &self.unit {
            LatticeUnit::U16(l) => l.next(node_id as u32, token_id as u16).map(|n| n as u64),
            LatticeUnit::U32(l) => l.next(node_id as u32, token_id as u32).map(|n| n as u64),
            LatticeUnit::U64(l) => l.next(node_id as u32, token_id).map(|n| n as u64),
        }
    }

    fn memory_usage(&self) -> usize {
        match &self.unit {
            LatticeUnit::U16(l) => l.memory_usage(),
            LatticeUnit::U32(l) => l.memory_usage(),
            LatticeUnit::U64(l) => l.memory_usage(),
        }
    }
}
