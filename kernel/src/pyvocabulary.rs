use pyo3::prelude::*;
use pyo3::types::PyType;
use std::sync::Arc;

use crate::vocabulary::Vocabulary;

type T = u32;

#[pyclass(name = "Vocabulary")]
#[derive(Clone)]
pub struct PyVocabulary {
    pub unit: Arc<Vocabulary<T>>,
}

#[pymethods]
impl PyVocabulary {
    #[new]
    fn new(data: &[u8], eos_id: u64) -> PyResult<Self> {
        let v = Vocabulary::new(data, eos_id as T)
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Vocabulary"))?;

        Ok(PyVocabulary { unit: Arc::new(v) })
    }

    #[classmethod]
    fn from_file_path(_cls: &Bound<'_, PyType>, _py: Python<'_>, file_path: &str, eos_id: u64) -> PyResult<Self> {
        let v = Vocabulary::from_file_path(file_path, eos_id as T)
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Vocabulary from file"))?;

        Ok(PyVocabulary { unit: Arc::new(v) })
    }

    fn get_token_by_id(&self, id: u64) -> Option<String> {
        self.unit.get_token_by_id(id as T).map(|s| s.to_string())
    }

    fn get_id_by_token(&self, token: &str) -> Option<u64> {
        self.unit.get_id_by_token(token).map(|id| id as u64)
    }

    fn get_eos_id(&self) -> u64 {
        self.unit.get_eos_id() as u64
    }

    fn get_tokens(&self) -> Vec<String> {
        self.unit.get_tokens().iter().map(|s| s.to_string()).collect()
    }

    fn get_ids(&self) -> Vec<u64> {
        self.unit.get_ids().iter().map(|&id| id as u64).collect()
    }

    fn get_token_by_idx(&self, idx: usize) -> Option<String> {
        self.unit.get_token_by_idx(idx).map(|s| s.to_string())
    }

    fn get_id_by_idx(&self, idx: usize) -> Option<u64> {
        self.unit.get_id_by_idx(idx).map(|id| id as u64)
    }
}
