use pyo3::prelude::*;
use pyo3::types::PyType;
use std::sync::Arc;

use crate::vocabulary::Vocabulary;

#[derive(Clone)]
pub enum VocabularyUnit {
    U16(Arc<Vocabulary<u16>>),
    U32(Arc<Vocabulary<u32>>),
    U64(Arc<Vocabulary<u64>>),
}

#[pyclass(name = "Vocabulary")]
#[derive(Clone)]
pub struct PyVocabulary {
    pub unit: VocabularyUnit,
}

#[pymethods]
impl PyVocabulary {
    #[new]
    fn new(data: &[u8], eos_id: u64, t_size: usize) -> PyResult<Self> {
        let unit = match t_size {
            2 => {
                let v = Vocabulary::new(data, eos_id as u16)
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Vocabulary<u16>"))?;

                VocabularyUnit::U16(Arc::new(v))
            },
            4 => {
                let v = Vocabulary::new(data, eos_id as u32)
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Vocabulary<u32>"))?;

                VocabularyUnit::U32(Arc::new(v))
            },
            8 => {
                let v = Vocabulary::new(data, eos_id)
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Vocabulary<u64>"))?;

                VocabularyUnit::U64(Arc::new(v))
            },
            _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("t_size must be 2 (u16), 4 (u32) or 8 (u64)")),
        };

        Ok(PyVocabulary { unit })
    }

    #[classmethod]
    fn from_file_path(_cls: &Bound<'_, PyType>, _py: Python<'_>, file_path: &str, eos_id: u64, t_size: usize) -> PyResult<Self> {
        let unit = match t_size {
            2 => {
                let v = Vocabulary::from_file_path(file_path, eos_id as u16)
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Vocabulary<u16> from file"))?;

                VocabularyUnit::U16(Arc::new(v))
            },
            4 => {
                let v = Vocabulary::from_file_path(file_path, eos_id as u32)
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Vocabulary<u32> from file"))?;

                VocabularyUnit::U32(Arc::new(v))
            },
            8 => {
                let v = Vocabulary::from_file_path(file_path, eos_id)
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Vocabulary<u64> from file"))?;

                VocabularyUnit::U64(Arc::new(v))
            },
            _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("t_size must be 2 (u16), 4 (u32) or 8 (u64)")),
        };

        Ok(PyVocabulary { unit })
    }

    fn get_token_by_id(&self, id: u64) -> Option<String> {
        match &self.unit {
            VocabularyUnit::U16(v) => v.get_token_by_id(id as u16).map(|s| s.to_string()),
            VocabularyUnit::U32(v) => v.get_token_by_id(id as u32).map(|s| s.to_string()),
            VocabularyUnit::U64(v) => v.get_token_by_id(id).map(|s| s.to_string()),
        }
    }

    fn get_id_by_token(&self, token: &str) -> Option<u64> {
        match &self.unit {
            VocabularyUnit::U16(v) => v.get_id_by_token(token).map(|id| id as u64),
            VocabularyUnit::U32(v) => v.get_id_by_token(token).map(|id| id as u64),
            VocabularyUnit::U64(v) => v.get_id_by_token(token),
        }
    }

    fn get_eos_id(&self) -> u64 {
        match &self.unit {
            VocabularyUnit::U16(v) => v.get_eos_id() as u64,
            VocabularyUnit::U32(v) => v.get_eos_id() as u64,
            VocabularyUnit::U64(v) => v.get_eos_id(),
        }
    }
}
