//! The head pool, exposed to Python.
//!
//! The interesting half is the resolver bridge. A feed runs with the GIL
//! dropped, so each notification takes it back, calls into Python and lets it
//! go again. A callback that raises must not unwind through Rust, so the error
//! is parked, the runner is told to stop asking, and it is re-raised once the
//! feed has returned.

use numpy::{PyArray1, PyArrayMethods};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use crate::number::Number;
use crate::pyfactory::{draft_from_py, PyFactory, D, N, T};
use crate::runtime::factory::Factory;
use crate::runtime::head::Head;
use crate::runtime::resolver::{Expansion, Report, Request, Resolver};
use crate::runtime::runner::Runner;

/// What a head carries for the library on the other side. The kernel never
/// looks inside it.
type Payload = Py<PyAny>;

/// An index to walk next, named either by id or by the spec to build it from.
fn request_from_py(spec: &Bound<'_, PyAny>, payload: Payload) -> PyResult<Request<Payload>> {
    if let Ok(index_id) = spec.extract::<u64>() {
        return Ok(Request::existing(index_id, payload));
    }

    Ok(Request::new(draft_from_py(spec)?, payload))
}

/// A snapshot of one active index.
#[pyclass(name = "Head")]
pub struct PyHead {
    #[pyo3(get)]
    pub id: u64,
    #[pyo3(get)]
    pub index_id: u64,
    #[pyo3(get)]
    pub node: u64,
    /// The index's label -- for a group, the shape of its inclusion.
    #[pyo3(get)]
    pub rule: String,
    #[pyo3(get)]
    pub matched: String,
    #[pyo3(get)]
    pub payload: Py<PyAny>,
}

#[pymethods]
impl PyHead {
    fn __repr__(&self) -> String {
        format!("Head({:?} @ {})", self.rule, self.node)
    }
}

/// Calls the Python resolver for the runner.
///
/// The runner runs with the GIL dropped, so each notification takes it back for
/// the duration of the callback and lets it go again. A callback that raises
/// stops the expansion: the error is held here and re-raised once `feed`
/// returns, because a panic must not cross back into Rust.
struct Bridge<'a> {
    callback: &'a Py<PyAny>,
    error: Mutex<Option<PyErr>>,
    failed: AtomicBool,
}

impl<'a> Bridge<'a> {
    fn new(callback: &'a Py<PyAny>) -> Self {
        Self {
            callback,
            error: Mutex::new(None),
            failed: AtomicBool::new(false),
        }
    }

    fn take_error(&self) -> Option<PyErr> {
        self.error.lock().unwrap().take()
    }

    fn call(&self, py: Python<'_>, report: &Report<'_, Payload>) -> PyResult<Expansion<Payload>> {
        let answer = self.callback.bind(py).call1((
            report.id,
            report.payload.bind(py),
            report.matched.as_str(),
        ))?;

        // `None` is the end of the graph; a list -- possibly empty -- is the
        // set of indexes that may follow.
        if answer.is_none() {
            return Ok(Expansion::Terminal);
        }

        let mut children: Vec<Request<Payload>> = Vec::new();

        for item in answer.iter()? {
            let item = item?;
            let spec = item.get_item(0)?;
            let payload: Payload = item.get_item(1)?.unbind();

            children.push(request_from_py(&spec, payload)?);
        }

        Ok(Expansion::Children(children))
    }
}

impl Resolver<Payload> for Bridge<'_> {
    fn resolve(&self, report: &Report<'_, Payload>) -> Expansion<Payload> {
        Python::with_gil(|py| match self.call(py, report) {
            Ok(expansion) => expansion,
            Err(error) => {
                *self.error.lock().unwrap() = Some(error);

                self.failed.store(true, Ordering::Relaxed);

                Expansion::Children(Vec::new())
            }
        })
    }

    fn aborted(&self) -> bool {
        self.failed.load(Ordering::Relaxed)
    }
}

/// The pool of active indexes, seen from Python.
///
/// Set a resolver, spawn the heads the generation starts from, then feed
/// tokens. Every time a head reaches the end of its index the resolver is
/// called with `(head_id, payload, matched)` and answers with either `None` --
/// nothing follows -- or a list of `(spec, payload)` pairs naming the indexes
/// that do.
#[pyclass(name = "Runner")]
pub struct PyRunner {
    factory: Arc<Factory<N, T, D>>,
    runner: Runner<N, T, D, Payload>,
    resolver: Option<Py<PyAny>>,
}

#[pymethods]
impl PyRunner {
    #[new]
    #[pyo3(signature = (factory, workers = 0))]
    fn new(factory: &PyFactory, workers: usize) -> PyResult<Self> {
        let unit: Arc<Factory<N, T, D>> = factory.unit.clone();

        let workers: usize = if workers == 0 {
            std::thread::available_parallelism()
                .map(|n| n.get())
                .unwrap_or(1)
        } else {
            workers
        };

        let runner = Runner::new(unit.clone(), workers)
            .ok_or_else(|| PyRuntimeError::new_err("Failed to build the worker pool"))?;

        Ok(PyRunner {
            factory: unit,
            runner,
            resolver: None,
        })
    }

    /// Register the callable the runner notifies when a head reaches the end of
    /// its index.
    fn set_resolver(&mut self, callback: Py<PyAny>) {
        self.resolver = Some(callback);
    }

    #[getter]
    fn factory(&self) -> PyFactory {
        PyFactory {
            unit: self.factory.clone(),
        }
    }

    #[getter]
    fn workers(&self) -> usize {
        self.runner.workers()
    }

    /// Put an index to work, given either its id or the spec to build it from.
    /// `None` when the spec cannot be built or the id names nothing.
    fn spawn(
        &mut self,
        py: Python<'_>,
        spec: &Bound<'_, PyAny>,
        payload: Py<PyAny>,
    ) -> PyResult<Option<u64>> {
        if let Ok(index_id) = spec.extract::<u64>() {
            return Ok(self.runner.spawn(index_id, payload));
        }

        let draft = draft_from_py(spec)?;
        let factory: Arc<Factory<N, T, D>> = self.factory.clone();

        let Some(index_id) = py.allow_threads(move || factory.create(&draft)) else {
            return Ok(None);
        };

        Ok(self.runner.spawn(index_id, payload))
    }

    /// Build a batch of `(spec, payload)` pairs on the workers and put each to
    /// work. Specs that cannot be built are skipped.
    fn spawn_many(&mut self, py: Python<'_>, items: &Bound<'_, PyAny>) -> PyResult<Vec<u64>> {
        let mut requests: Vec<Request<Payload>> = Vec::new();

        for item in items.iter()? {
            let item = item?;
            let spec = item.get_item(0)?;
            let payload: Payload = item.get_item(1)?.unbind();

            requests.push(request_from_py(&spec, payload)?);
        }

        let runner: &mut Runner<N, T, D, Payload> = &mut self.runner;

        Ok(py.allow_threads(move || runner.spawn_many(requests)))
    }

    /// Consume a token, advancing every head and resolving the ones that reach
    /// the end of their index. Returns whether any head accepted it.
    fn feed(&mut self, py: Python<'_>, token_id: u64) -> PyResult<bool> {
        let Some(callback) = self.resolver.as_ref().map(|hook| hook.clone_ref(py)) else {
            return Err(PyRuntimeError::new_err("No resolver is set"));
        };

        let token: T = T::from_usize(token_id as usize);
        let bridge: Bridge<'_> = Bridge::new(&callback);
        let runner: &mut Runner<N, T, D, Payload> = &mut self.runner;

        let accepted: bool = py.allow_threads(|| runner.feed(token, &bridge));

        if let Some(error) = bridge.take_error() {
            return Err(error);
        }

        Ok(accepted)
    }

    /// Run the resolve loop without consuming a token, for heads spawned onto
    /// an index that accepts straight away.
    fn settle(&mut self, py: Python<'_>) -> PyResult<()> {
        let Some(callback) = self.resolver.as_ref().map(|hook| hook.clone_ref(py)) else {
            return Err(PyRuntimeError::new_err("No resolver is set"));
        };

        let bridge: Bridge<'_> = Bridge::new(&callback);
        let runner: &mut Runner<N, T, D, Payload> = &mut self.runner;

        py.allow_threads(|| runner.settle(&bridge));

        match bridge.take_error() {
            Some(error) => Err(error),
            None => Ok(()),
        }
    }

    /// Every token id at least one live head would accept.
    fn routes<'py>(&self, py: Python<'py>) -> Bound<'py, PyArray1<u64>> {
        let runner: &Runner<N, T, D, Payload> = &self.runner;
        let routes: Vec<T> = py.allow_threads(|| runner.routes());

        PyArray1::from_vec_bound(
            py,
            routes.iter().map(|&id| id.to_usize() as u64).collect(),
        )
    }

    fn heads(&self, py: Python<'_>) -> Vec<PyHead> {
        self.runner
            .heads()
            .iter()
            .map(|head| self.view(py, head))
            .collect()
    }

    fn head(&self, py: Python<'_>, head_id: u64) -> Option<PyHead> {
        self.runner.head(head_id).map(|head| self.view(py, head))
    }

    fn kill(&mut self, head_id: u64) -> bool {
        self.runner.kill(head_id)
    }

    fn clear(&mut self) {
        self.runner.clear();
    }

    fn is_completed(&self) -> bool {
        self.runner.is_completed()
    }

    /// The tokens the runner has accepted, as text.
    fn matched(&self) -> String {
        self.runner.matched()
    }

    /// Rounds of the resolve loop, heads notified, and heads created.
    #[getter]
    fn stats(&self) -> (usize, usize, usize) {
        self.runner.stats()
    }

    fn __len__(&self) -> usize {
        self.runner.len()
    }
}

impl PyRunner {
    fn view(&self, py: Python<'_>, head: &Head<N, T, D, Payload>) -> PyHead {
        PyHead {
            id: head.id(),
            index_id: head.index_id(),
            node: head.node().to_usize() as u64,
            rule: self.factory.label(head.index_id()).unwrap_or_default(),
            matched: head.matched(self.factory.vocabulary()),
            payload: head.payload().clone_ref(py),
        }
    }
}
