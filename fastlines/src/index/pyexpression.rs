use pyo3::prelude::*;
use numpy::{PyArray1, PyArrayMethods};
use toktrie::TokTrie;
use std::sync::Arc;
use std::borrow::Cow;

use crate::pyvocabulary::{PyVocabulary, VocabularyUnit};
use crate::dfa::fasthashdfa::FastHashDFA;
use crate::dfa::doublehashdfa::DoubleHashDFA;
use crate::dfa::flatdfa::FlatDFA;
use crate::index::index::Index;
use crate::index::expression::Expression;
use crate::number::Number;

#[derive(Clone)]
pub enum ExpressionUnit {
    FhU16U16(Arc<Expression<u16, u16, FastHashDFA<u16, u16>>>),
    FhU32U16(Arc<Expression<u32, u16, FastHashDFA<u32, u16>>>),
    FhU64U16(Arc<Expression<u64, u16, FastHashDFA<u64, u16>>>),
    FhU16U32(Arc<Expression<u16, u32, FastHashDFA<u16, u32>>>),
    FhU32U32(Arc<Expression<u32, u32, FastHashDFA<u32, u32>>>),
    FhU64U32(Arc<Expression<u64, u32, FastHashDFA<u64, u32>>>),
    FhU16U64(Arc<Expression<u16, u64, FastHashDFA<u16, u64>>>),
    FhU32U64(Arc<Expression<u32, u64, FastHashDFA<u32, u64>>>),
    FhU64U64(Arc<Expression<u64, u64, FastHashDFA<u64, u64>>>),

    DoubleU16U16(Arc<Expression<u16, u16, DoubleHashDFA<u16, u16>>>),
    DoubleU32U16(Arc<Expression<u32, u16, DoubleHashDFA<u32, u16>>>),
    DoubleU64U16(Arc<Expression<u64, u16, DoubleHashDFA<u64, u16>>>),
    DoubleU16U32(Arc<Expression<u16, u32, DoubleHashDFA<u16, u32>>>),
    DoubleU32U32(Arc<Expression<u32, u32, DoubleHashDFA<u32, u32>>>),
    DoubleU64U32(Arc<Expression<u64, u32, DoubleHashDFA<u64, u32>>>),
    DoubleU16U64(Arc<Expression<u16, u64, DoubleHashDFA<u16, u64>>>),
    DoubleU32U64(Arc<Expression<u32, u64, DoubleHashDFA<u32, u64>>>),
    DoubleU64U64(Arc<Expression<u64, u64, DoubleHashDFA<u64, u64>>>),

    FlatU16U16(Arc<Expression<u16, u16, FlatDFA<u16, u16>>>),
    FlatU32U16(Arc<Expression<u32, u16, FlatDFA<u32, u16>>>),
    FlatU64U16(Arc<Expression<u64, u16, FlatDFA<u64, u16>>>),
    FlatU16U32(Arc<Expression<u16, u32, FlatDFA<u16, u32>>>),
    FlatU32U32(Arc<Expression<u32, u32, FlatDFA<u32, u32>>>),
    FlatU64U32(Arc<Expression<u64, u32, FlatDFA<u64, u32>>>),
    FlatU16U64(Arc<Expression<u16, u64, FlatDFA<u16, u64>>>),
    FlatU32U64(Arc<Expression<u32, u64, FlatDFA<u32, u64>>>),
    FlatU64U64(Arc<Expression<u64, u64, FlatDFA<u64, u64>>>),
}

impl ExpressionUnit {
    pub fn start(&self) -> u64 {
        macro_rules! call_start {
            ($e:expr) => { $e.start().to_usize() as u64 }
        }

        match self {
            Self::FhU16U16(e) => call_start!(e), Self::FhU32U16(e) => call_start!(e), Self::FhU64U16(e) => call_start!(e),
            Self::FhU16U32(e) => call_start!(e), Self::FhU32U32(e) => call_start!(e), Self::FhU64U32(e) => call_start!(e),
            Self::FhU16U64(e) => call_start!(e), Self::FhU32U64(e) => call_start!(e), Self::FhU64U64(e) => call_start!(e),

            Self::DoubleU16U16(e) => call_start!(e), Self::DoubleU32U16(e) => call_start!(e), Self::DoubleU64U16(e) => call_start!(e),
            Self::DoubleU16U32(e) => call_start!(e), Self::DoubleU32U32(e) => call_start!(e), Self::DoubleU64U32(e) => call_start!(e),
            Self::DoubleU16U64(e) => call_start!(e), Self::DoubleU32U64(e) => call_start!(e), Self::DoubleU64U64(e) => call_start!(e),

            Self::FlatU16U16(e) => call_start!(e), Self::FlatU32U16(e) => call_start!(e), Self::FlatU64U16(e) => call_start!(e),
            Self::FlatU16U32(e) => call_start!(e), Self::FlatU32U32(e) => call_start!(e), Self::FlatU64U32(e) => call_start!(e),
            Self::FlatU16U64(e) => call_start!(e), Self::FlatU32U64(e) => call_start!(e), Self::FlatU64U64(e) => call_start!(e),
        }
    }

    pub fn next(&self, node_id: u64, token_id: u64) -> Option<u64> {
        macro_rules! call_next {
            ($e:expr, $N:ty, $T:ty) => {
                $e.next(<$N>::from_usize(node_id as usize), <$T>::from_usize(token_id as usize))
                  .map(|n| n.to_usize() as u64)
            }
        }

        match self {
            Self::FhU16U16(e) => call_next!(e, u16, u16), Self::FhU32U16(e) => call_next!(e, u32, u16), Self::FhU64U16(e) => call_next!(e, u64, u16),
            Self::FhU16U32(e) => call_next!(e, u16, u32), Self::FhU32U32(e) => call_next!(e, u32, u32), Self::FhU64U32(e) => call_next!(e, u64, u32),
            Self::FhU16U64(e) => call_next!(e, u16, u64), Self::FhU32U64(e) => call_next!(e, u32, u64), Self::FhU64U64(e) => call_next!(e, u64, u64),

            Self::DoubleU16U16(e) => call_next!(e, u16, u16), Self::DoubleU32U16(e) => call_next!(e, u32, u16), Self::DoubleU64U16(e) => call_next!(e, u64, u16),
            Self::DoubleU16U32(e) => call_next!(e, u16, u32), Self::DoubleU32U32(e) => call_next!(e, u32, u32), Self::DoubleU64U32(e) => call_next!(e, u64, u32),
            Self::DoubleU16U64(e) => call_next!(e, u16, u64), Self::DoubleU32U64(e) => call_next!(e, u32, u64), Self::DoubleU64U64(e) => call_next!(e, u64, u64),

            Self::FlatU16U16(e) => call_next!(e, u16, u16), Self::FlatU32U16(e) => call_next!(e, u32, u16), Self::FlatU64U16(e) => call_next!(e, u64, u16),
            Self::FlatU16U32(e) => call_next!(e, u16, u32), Self::FlatU32U32(e) => call_next!(e, u32, u32), Self::FlatU64U32(e) => call_next!(e, u64, u32),
            Self::FlatU16U64(e) => call_next!(e, u16, u64), Self::FlatU32U64(e) => call_next!(e, u32, u64), Self::FlatU64U64(e) => call_next!(e, u64, u64),
        }
    }

    pub fn memory_usage(&self) -> usize {
        macro_rules! call_mem {
            ($e:expr) => { $e.memory_usage() }
        }

        match self {
            Self::FhU16U16(e) => call_mem!(e), Self::FhU32U16(e) => call_mem!(e), Self::FhU64U16(e) => call_mem!(e),
            Self::FhU16U32(e) => call_mem!(e), Self::FhU32U32(e) => call_mem!(e), Self::FhU64U32(e) => call_mem!(e),
            Self::FhU16U64(e) => call_mem!(e), Self::FhU32U64(e) => call_mem!(e), Self::FhU64U64(e) => call_mem!(e),

            Self::DoubleU16U16(e) => call_mem!(e), Self::DoubleU32U16(e) => call_mem!(e), Self::DoubleU64U16(e) => call_mem!(e),
            Self::DoubleU16U32(e) => call_mem!(e), Self::DoubleU32U32(e) => call_mem!(e), Self::DoubleU64U32(e) => call_mem!(e),
            Self::DoubleU16U64(e) => call_mem!(e), Self::DoubleU32U64(e) => call_mem!(e), Self::DoubleU64U64(e) => call_mem!(e),

            Self::FlatU16U16(e) => call_mem!(e), Self::FlatU32U16(e) => call_mem!(e), Self::FlatU64U16(e) => call_mem!(e),
            Self::FlatU16U32(e) => call_mem!(e), Self::FlatU32U32(e) => call_mem!(e), Self::FlatU64U32(e) => call_mem!(e),
            Self::FlatU16U64(e) => call_mem!(e), Self::FlatU32U64(e) => call_mem!(e), Self::FlatU64U64(e) => call_mem!(e),
        }
    }

    pub fn transitions<'a>(&'a self, node_id: u64) -> Option<Cow<'a, [u64]>> {
        macro_rules! call_trans {
            ($e:expr, $N:ty) => {
                $e.transitions(<$N>::from_usize(node_id as usize)).map(|c| match c {
                    Cow::Borrowed(s) => Cow::Owned(s.iter().map(|x| x.to_usize() as u64).collect()),
                    Cow::Owned(v) => Cow::Owned(v.into_iter().map(|x| x.to_usize() as u64).collect()),
                })
            }
        }

        match self {
            Self::FhU16U16(e) => call_trans!(e, u16), Self::FhU32U16(e) => call_trans!(e, u32), Self::FhU64U16(e) => call_trans!(e, u64),
            Self::FhU16U32(e) => call_trans!(e, u16), Self::FhU32U32(e) => call_trans!(e, u32), Self::FhU64U32(e) => call_trans!(e, u64),
            Self::FhU16U64(e) => call_trans!(e, u16), Self::FhU32U64(e) => call_trans!(e, u32), Self::FhU64U64(e) => call_trans!(e, u64),

            Self::DoubleU16U16(e) => call_trans!(e, u16), Self::DoubleU32U16(e) => call_trans!(e, u32), Self::DoubleU64U16(e) => call_trans!(e, u64),
            Self::DoubleU16U32(e) => call_trans!(e, u16), Self::DoubleU32U32(e) => call_trans!(e, u32), Self::DoubleU64U32(e) => call_trans!(e, u64),
            Self::DoubleU16U64(e) => call_trans!(e, u16), Self::DoubleU32U64(e) => call_trans!(e, u32), Self::DoubleU64U64(e) => call_trans!(e, u64),

            Self::FlatU16U16(e) => call_trans!(e, u16), Self::FlatU32U16(e) => call_trans!(e, u32), Self::FlatU64U16(e) => call_trans!(e, u64),
            Self::FlatU16U32(e) => call_trans!(e, u16), Self::FlatU32U32(e) => call_trans!(e, u32), Self::FlatU64U32(e) => call_trans!(e, u64),
            Self::FlatU16U64(e) => call_trans!(e, u16), Self::FlatU32U64(e) => call_trans!(e, u32), Self::FlatU64U64(e) => call_trans!(e, u64),
        }
    }
}

#[pyclass(name = "TokTrie")]
#[derive(Clone)]
pub struct PyTokTrie {
    pub unit: Arc<TokTrie>,
    pub dfa_type: u8,
    pub n_size: u8,
    pub t_size: u8,
}

#[pymethods]
impl PyTokTrie {
    #[staticmethod]
    fn new(vocabulary_py: &PyVocabulary, dfa_type: u8, n_size: u8, t_size: u8) -> PyResult<Self> {
        let trie = match &vocabulary_py.unit {
            VocabularyUnit::U16(v) => Expression::<u16, u16, FastHashDFA<u16, u16>>::base(v.clone()),
            VocabularyUnit::U32(v) => Expression::<u16, u32, FastHashDFA<u16, u32>>::base(v.clone()),
            VocabularyUnit::U64(v) => Expression::<u16, u64, FastHashDFA<u16, u64>>::base(v.clone()),
        }.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to build TokTrie base"))?;

        Ok(PyTokTrie {
            unit: Arc::new(trie),
            dfa_type,
            n_size,
            t_size,
        })
    }
}

#[pyclass(name = "Expression")]
#[derive(Clone)]
pub struct PyExpression {
    unit: ExpressionUnit,
}

#[pymethods]
impl PyExpression {
    #[new]
    fn new(input: &str, vocabulary_py: &PyVocabulary, toktrie_base: &PyTokTrie) -> PyResult<Self> {
        let d = toktrie_base.dfa_type;
        let n = toktrie_base.n_size;
        let t = toktrie_base.t_size;

        macro_rules! make_exp {
            ($Var:ident, $N:ty, $T:ty, $DFA:ident, $VocabUnit:ident) => {
                if let VocabularyUnit::$VocabUnit(v) = &vocabulary_py.unit {
                    let e = Expression::<$N, $T, $DFA<$N, $T>>::new(input, v.clone(), &toktrie_base.unit)
                        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Failed to create Expression"))?;

                    return Ok(PyExpression { unit: ExpressionUnit::$Var(Arc::new(e)) });
                } else {
                    return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("Vocabulary T size mismatch with configuration"));
                }
            };
        }

        if d == 0 {
            match (n, t) {
                (2, 2) => make_exp!(FhU16U16, u16, u16, FastHashDFA, U16),
                (4, 2) => make_exp!(FhU32U16, u32, u16, FastHashDFA, U16),
                (8, 2) => make_exp!(FhU64U16, u64, u16, FastHashDFA, U16),
                (2, 4) => make_exp!(FhU16U32, u16, u32, FastHashDFA, U32),
                (4, 4) => make_exp!(FhU32U32, u32, u32, FastHashDFA, U32),
                (8, 4) => make_exp!(FhU64U32, u64, u32, FastHashDFA, U32),
                (2, 8) => make_exp!(FhU16U64, u16, u64, FastHashDFA, U64),
                (4, 8) => make_exp!(FhU32U64, u32, u64, FastHashDFA, U64),
                (8, 8) => make_exp!(FhU64U64, u64, u64, FastHashDFA, U64),
                _ => {},
            }
        } else if d == 1 {
            match (n, t) {
                (2, 2) => make_exp!(DoubleU16U16, u16, u16, DoubleHashDFA, U16),
                (4, 2) => make_exp!(DoubleU32U16, u32, u16, DoubleHashDFA, U16),
                (8, 2) => make_exp!(DoubleU64U16, u64, u16, DoubleHashDFA, U16),
                (2, 4) => make_exp!(DoubleU16U32, u16, u32, DoubleHashDFA, U32),
                (4, 4) => make_exp!(DoubleU32U32, u32, u32, DoubleHashDFA, U32),
                (8, 4) => make_exp!(DoubleU64U32, u64, u32, DoubleHashDFA, U32),
                (2, 8) => make_exp!(DoubleU16U64, u16, u64, DoubleHashDFA, U64),
                (4, 8) => make_exp!(DoubleU32U64, u32, u64, DoubleHashDFA, U64),
                (8, 8) => make_exp!(DoubleU64U64, u64, u64, DoubleHashDFA, U64),
                _ => {},
            }
        } else if d == 2 {
            match (n, t) {
                (2, 2) => make_exp!(FlatU16U16, u16, u16, FlatDFA, U16),
                (4, 2) => make_exp!(FlatU32U16, u32, u16, FlatDFA, U16),
                (8, 2) => make_exp!(FlatU64U16, u64, u16, FlatDFA, U16),
                (2, 4) => make_exp!(FlatU16U32, u16, u32, FlatDFA, U32),
                (4, 4) => make_exp!(FlatU32U32, u32, u32, FlatDFA, U32),
                (8, 4) => make_exp!(FlatU64U32, u64, u32, FlatDFA, U32),
                (2, 8) => make_exp!(FlatU16U64, u16, u64, FlatDFA, U64),
                (4, 8) => make_exp!(FlatU32U64, u32, u64, FlatDFA, U64),
                (8, 8) => make_exp!(FlatU64U64, u64, u64, FlatDFA, U64),
                _ => {},
            }
        }

        Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Unsupported configuration: Type={}, N={}, T={}", d, n, t)
        ))
    }

    fn start(&self) -> u64 {
        self.unit.start()
    }

    fn transitions<'py>(&self, py: Python<'py>, node_id: u64) -> PyResult<Bound<'py, PyArray1<u64>>> {
        let t = self.unit.transitions(node_id);

        let v: Vec<u64> = match t {
            Some(tv) => tv.into_owned(),
            None => Vec::new(),
        };

        Ok(PyArray1::from_vec_bound(py, v))
    }

    fn next(&self, node_id: u64, token_id: u64) -> Option<u64> {
        self.unit.next(node_id, token_id)
    }

    fn memory_usage(&self) -> usize {
        self.unit.memory_usage()
    }
}
