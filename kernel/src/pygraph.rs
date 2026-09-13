//! `Multigraph`, exposed to Python.
//!
//! Labels cross as whatever object the caller put on the edge and come back
//! unexamined, exactly as a head's payload does in `pyrunner`.

use pyo3::prelude::*;
use pyo3::types::PyAnyMethods;

use crate::graph::multigraph::Multigraph;

type Label = Py<PyAny>;

#[pyclass(name = "Multigraph")]
pub struct PyMultigraph {
    graph: Multigraph<Label>,
}

impl PyMultigraph {
    fn wrap(graph: Multigraph<Label>) -> Self {
        Self { graph }
    }
}

#[pymethods]
impl PyMultigraph {
    /// Build from an iterable of `(source, target, label)` triples.
    #[new]
    #[pyo3(signature = (edges = None))]
    fn new(edges: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        let mut triples: Vec<(String, String, Label)> = Vec::new();

        if let Some(edges) = edges {
            for item in edges.try_iter()? {
                let item = item?;
                let source: String = item.get_item(0)?.extract()?;
                let target: String = item.get_item(1)?.extract()?;
                let label: Label = item.get_item(2)?.unbind();

                triples.push((source, target, label));
            }
        }

        Ok(Self::wrap(Multigraph::new(triples)))
    }

    /// A clone each branch of the syntax graph can merge into freely, sharing
    /// both the edges and the contraction state until one of them writes.
    fn copy(&self) -> Self {
        Self::wrap(self.graph.copy())
    }

    fn __contains__(&self, node: &str) -> bool {
        self.graph.contains(node)
    }

    fn nodes(&self) -> Vec<&str> {
        self.graph.nodes()
    }

    /// Every edge incident to `node`, as `(neighbour, label)`.
    fn edges(&self, py: Python<'_>, node: &str) -> Vec<(&str, Label)> {
        self.graph
            .edges(node)
            .into_iter()
            .map(|(name, label)| (name, label.clone_ref(py)))
            .collect()
    }

    /// Fold `other` into `head`. Edges between the two become loops and go.
    fn merge_vertices(&mut self, head: &str, other: &str) -> bool {
        self.graph.merge_vertices(head, other)
    }

    fn __len__(&self) -> usize {
        self.graph.vertex_count()
    }

    fn edge_count(&self) -> usize {
        self.graph.edge_count()
    }

    /// What this copy costs on its own; the shared base is `base_memory_usage`.
    fn memory_usage(&self) -> usize {
        self.graph.memory_usage()
    }

    fn base_memory_usage(&self) -> usize {
        self.graph.base_memory_usage()
    }

    fn __repr__(&self) -> String {
        format!(
            "Multigraph({} vertices, {} edges)",
            self.graph.vertex_count(),
            self.graph.edge_count()
        )
    }
}
