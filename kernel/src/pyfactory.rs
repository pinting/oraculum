//! The index registry, exposed to Python.
//!
//! This is where the widths the Python extension is compiled with are fixed:
//! `u32` node ids, `u32` token ids and `FlatDFA` as the transition layout. The
//! layout is a type parameter rather than a setting, so choosing another one
//! means rebuilding; `pyrunner` takes all three from here.
//!
//! Every entry point that builds anything drops the GIL first. Building is
//! measured in milliseconds and touches no Python state, so a caller with
//! threads can build indexes in parallel and the runner can spread a batch over
//! its worker pool.

use pyo3::exceptions::{PyIndexError, PyValueError};
use pyo3::prelude::*;
use std::sync::Arc;

use crate::dfa::flatdfa::FlatDFA;
use crate::index::pyexpression::PyTokTrie;
use crate::index::pylattice::PyAhoCorasick;
use crate::number::Number;
use crate::pyvocabulary::PyVocabulary;
use crate::runtime::factory::{Draft, Factory, IndexId};

pub type N = u32;
pub type T = u32;
pub type D = FlatDFA<N, T>;

/// Turn the Python description of an index into a `Draft`.
///
/// A spec is a tuple naming the kind and its arguments:
///
///     ("lattice", "SELECT")
///     ("expression", "[a-zA-Z_][a-zA-Z0-9_]*")
///     ("group", include_id, [exclude_id, ...])
///
/// A group is described by the ids of indexes that already exist, which is what
/// lets a group hold other groups.
pub fn draft_from_py(spec: &Bound<'_, PyAny>) -> PyResult<Draft> {
    let kind: String = spec.get_item(0)?.extract()?;

    match kind.as_str() {
        "lattice" => Ok(Draft::Lattice(spec.get_item(1)?.extract()?)),
        "expression" => Ok(Draft::Expression(spec.get_item(1)?.extract()?)),
        "group" => Ok(Draft::Group {
            include: spec.get_item(1)?.extract()?,
            excludes: spec.get_item(2)?.extract()?,
        }),
        other => Err(PyValueError::new_err(format!(
            "Unknown index kind: {other}"
        ))),
    }
}

fn drafts_from_py(specs: &Bound<'_, PyAny>) -> PyResult<Vec<Draft>> {
    let mut drafts: Vec<Draft> = Vec::new();

    for spec in specs.try_iter()? {
        drafts.push(draft_from_py(&spec?)?);
    }

    Ok(drafts)
}

/// The index registry, seen from Python.
///
/// `Lattice` and `Expression` are still there for callers that want to own an
/// index outright. The factory is for callers that do not: it builds the index,
/// keeps it, and answers with an id.
#[pyclass(name = "Factory", from_py_object)]
#[derive(Clone)]
pub struct PyFactory {
    pub unit: Arc<Factory<N, T, D>>,
}

#[pymethods]
impl PyFactory {
    /// Building the Aho-Corasick and TokTrie bases scans the whole vocabulary,
    /// so the GIL is dropped for it.
    #[new]
    #[pyo3(signature = (vocabulary, cache = true))]
    fn new(py: Python<'_>, vocabulary: &PyVocabulary, cache: bool) -> PyResult<Self> {
        let vocabulary = vocabulary.unit.clone();

        let factory = py
            .detach(move || Factory::<N, T, D>::new(vocabulary, cache))
            .ok_or_else(|| PyValueError::new_err("Failed to create Factory"))?;

        Ok(PyFactory {
            unit: Arc::new(factory),
        })
    }

    /// A factory over bases that have already been built elsewhere.
    #[staticmethod]
    #[pyo3(signature = (vocabulary, ac_base, trie_base, cache = true))]
    fn with_bases(
        vocabulary: &PyVocabulary,
        ac_base: &PyAhoCorasick,
        trie_base: &PyTokTrie,
        cache: bool,
    ) -> Self {
        PyFactory {
            unit: Arc::new(Factory::<N, T, D>::with_bases(
                vocabulary.unit.clone(),
                ac_base.unit.clone(),
                trie_base.unit.clone(),
                cache,
            )),
        }
    }

    /// A factory with an empty registry over the same bases.
    ///
    /// The bases cost roughly half a second to build and depend only on the
    /// vocabulary, so a cold registry should never pay for them twice.
    #[pyo3(signature = (cache = true))]
    fn fork(&self, cache: bool) -> Self {
        PyFactory {
            unit: Arc::new(self.unit.fork(cache)),
        }
    }

    /// Build the index for `spec`, or return the id of the one that already
    /// answers it. `None` when the spec cannot be built.
    fn create(&self, py: Python<'_>, spec: &Bound<'_, PyAny>) -> PyResult<Option<u64>> {
        let draft: Draft = draft_from_py(spec)?;
        let factory: Arc<Factory<N, T, D>> = self.unit.clone();

        Ok(py.detach(move || factory.create(&draft)))
    }

    /// Build a batch, spread over the worker pool.
    fn create_many(&self, py: Python<'_>, specs: &Bound<'_, PyAny>) -> PyResult<Vec<Option<u64>>> {
        let drafts: Vec<Draft> = drafts_from_py(specs)?;
        let factory: Arc<Factory<N, T, D>> = self.unit.clone();

        Ok(py.detach(move || factory.create_many(&drafts)))
    }

    fn lattice(&self, py: Python<'_>, word: &str) -> Option<u64> {
        let word: String = word.to_string();
        let factory: Arc<Factory<N, T, D>> = self.unit.clone();

        py.detach(move || factory.create_lattice(&word))
    }

    fn expression(&self, py: Python<'_>, pattern: &str) -> Option<u64> {
        let pattern: String = pattern.to_string();
        let factory: Arc<Factory<N, T, D>> = self.unit.clone();

        py.detach(move || factory.create_expression(&pattern))
    }

    fn group(&self, py: Python<'_>, include: u64, excludes: Vec<u64>) -> Option<u64> {
        let factory: Arc<Factory<N, T, D>> = self.unit.clone();

        py.detach(move || factory.create_group(include, excludes))
    }

    /// Whether `create` would return without building anything.
    fn is_cached(&self, spec: &Bound<'_, PyAny>) -> PyResult<bool> {
        Ok(self.unit.is_cached(&draft_from_py(spec)?))
    }

    /// Indexes actually constructed, ignoring the ones served from cache.
    #[getter]
    fn builds(&self) -> usize {
        self.unit.builds()
    }

    fn label(&self, index_id: u64) -> PyResult<String> {
        self.unit
            .label(index_id)
            .ok_or_else(|| PyIndexError::new_err(format!("No index {index_id}")))
    }

    fn node_count(&self, index_id: u64) -> PyResult<u64> {
        self.unit
            .node_count(index_id)
            .map(|count| count.to_usize() as u64)
            .ok_or_else(|| PyIndexError::new_err(format!("No index {index_id}")))
    }

    fn memory_usage(&self, index_id: u64) -> PyResult<usize> {
        self.unit
            .memory_usage(index_id)
            .ok_or_else(|| PyIndexError::new_err(format!("No index {index_id}")))
    }

    fn is_group(&self, index_id: u64) -> PyResult<bool> {
        self.unit
            .get(index_id)
            .map(|unit| unit.is_group())
            .ok_or_else(|| PyIndexError::new_err(format!("No index {index_id}")))
    }

    fn __len__(&self) -> usize {
        self.unit.len()
    }
}

impl PyFactory {
    pub fn factory(&self) -> &Arc<Factory<N, T, D>> {
        &self.unit
    }

    pub fn index_id(id: u64) -> IndexId {
        id
    }
}
