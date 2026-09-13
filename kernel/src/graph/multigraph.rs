//! An undirected multigraph that is only ever contracted, never grown.
//!
//! Join resolution walks a foreign key graph: the FROM clause opens at some
//! table, and every join folds a neighbour into it, after which the pair
//! behaves as one vertex for further joins. That is vertex contraction, and it
//! is the *only* mutation - no vertex or edge is ever added once the graph has
//! been built from the schema.
//!
//! Which is worth exploiting, because the operation that actually dominates is
//! `copy`. Every branch of the syntax graph needs its own graph to fold into,
//! and branches are speculative: the overwhelming majority are copied, looked
//! at and thrown away. A general purpose graph - SageMath's, or an adjacency
//! dict - has to deep copy its adjacency for each one.
//!
//! So the edges live in an immutable `Base` that every copy shares, and the
//! whole of the mutable state is one array: `class[v]` is the vertex `v` has
//! been folded into, itself when it has not been. That array is behind an `Arc`
//! too, so
//!
//!     copy            two reference count bumps, no allocation
//!     merge_vertices  one clone of an array of `u32`, then a linear pass
//!     edges           the class members' base incidence, mapped through it
//!
//! and a branch that never joins anything never allocates at all. Dropped loops
//! need no special handling either: an edge whose far end is in the same class
//! as the near end is simply not reported, which is the rule the SageMath graph
//! this replaces enforces by refusing loops outright.

use rustc_hash::FxHashMap as HashMap;
use std::sync::Arc;

pub type VertexId = u32;
pub type EdgeId = u32;

/// The part of the graph no contraction can touch.
struct Base<L> {
    names: Vec<String>,
    index: HashMap<String, VertexId>,
    endpoints: Vec<(VertexId, VertexId)>,
    labels: Vec<L>,
    /// Edges incident to each vertex as the graph was built, before any
    /// contraction. A vertex's current incidence is the union over its class.
    incident: Vec<Vec<EdgeId>>,
}

impl<L> Base<L> {
    fn vertex(&mut self, name: &str) -> VertexId {
        if let Some(&existing) = self.index.get(name) {
            return existing;
        }

        let id: VertexId = self.names.len() as VertexId;

        self.names.push(name.to_string());
        self.index.insert(name.to_string(), id);
        self.incident.push(Vec::new());

        id
    }
}

pub struct Multigraph<L> {
    base: Arc<Base<L>>,
    class: Arc<Vec<VertexId>>,
}

impl<L> Multigraph<L> {
    /// Build from `(source, target, label)` triples.
    ///
    /// Vertices come from the edges alone: a table no foreign key touches is
    /// not in the graph, and `contains` says so.
    pub fn new<I>(edges: I) -> Self
    where
        I: IntoIterator<Item = (String, String, L)>,
    {
        let mut base: Base<L> = Base {
            names: Vec::new(),
            index: HashMap::default(),
            endpoints: Vec::new(),
            labels: Vec::new(),
            incident: Vec::new(),
        };

        for (source, target, label) in edges {
            let left: VertexId = base.vertex(&source);
            let right: VertexId = base.vertex(&target);
            let id: EdgeId = base.endpoints.len() as EdgeId;

            base.endpoints.push((left, right));
            base.labels.push(label);
            base.incident[left as usize].push(id);

            if right != left {
                base.incident[right as usize].push(id);
            }
        }

        let class: Vec<VertexId> = (0..base.names.len() as VertexId).collect();

        Self {
            base: Arc::new(base),
            class: Arc::new(class),
        }
    }

    /// A clone every branch can fold into freely. Nothing is copied here: the
    /// edges are shared and the class array is shared until one of the two
    /// writes to it.
    pub fn copy(&self) -> Self {
        Self {
            base: Arc::clone(&self.base),
            class: Arc::clone(&self.class),
        }
    }

    /// Whether the name is a vertex that has not been folded into another.
    pub fn contains(&self, name: &str) -> bool {
        self.alive(name).is_some()
    }

    fn alive(&self, name: &str) -> Option<VertexId> {
        let &vertex = self.base.index.get(name)?;

        if self.class[vertex as usize] == vertex {
            Some(vertex)
        } else {
            None
        }
    }

    /// Every surviving vertex, sorted.
    pub fn nodes(&self) -> Vec<&str> {
        let mut names: Vec<&str> = self
            .class
            .iter()
            .enumerate()
            .filter(|&(vertex, &owner)| owner == vertex as VertexId)
            .map(|(vertex, _)| self.base.names[vertex].as_str())
            .collect();

        names.sort_unstable();

        names
    }

    /// Every edge incident to `name`, as `(neighbour, label)`.
    ///
    /// The class's members are found by a scan of the class array rather than
    /// by a list kept per class: the array is what a copy shares, and keeping
    /// anything else in step with it would put that something into every copy
    /// as well.
    pub fn edges(&self, name: &str) -> Vec<(&str, &L)> {
        let Some(head) = self.alive(name) else {
            return Vec::new();
        };

        let mut incident: Vec<(&str, &L)> = Vec::new();

        for (member, &owner) in self.class.iter().enumerate() {
            if owner != head {
                continue;
            }

            for &edge in &self.base.incident[member] {
                let (left, right) = self.base.endpoints[edge as usize];
                let far: VertexId = if left == member as VertexId { right } else { left };
                let target: VertexId = self.class[far as usize];

                // Both ends in this class: the edge is a loop now, and a loop
                // is not a join.
                if target == head {
                    continue;
                }

                incident.push((
                    self.base.names[target as usize].as_str(),
                    &self.base.labels[edge as usize],
                ));
            }
        }

        incident
    }

    /// Fold `other` into `head`, which keeps its name and gains its edges.
    ///
    /// A no-op unless both are vertices and both are still standing, matching
    /// what the adjacency dict and the SageMath graph both do with a vertex
    /// that is not there.
    pub fn merge_vertices(&mut self, head: &str, other: &str) -> bool {
        if head == other {
            return false;
        }

        let (Some(into), Some(from)) = (self.alive(head), self.alive(other)) else {
            return false;
        };

        let class: &mut Vec<VertexId> = Arc::make_mut(&mut self.class);

        for owner in class.iter_mut() {
            if *owner == from {
                *owner = into;
            }
        }

        true
    }

    pub fn vertex_count(&self) -> usize {
        self.class
            .iter()
            .enumerate()
            .filter(|&(vertex, &owner)| owner == vertex as VertexId)
            .count()
    }

    pub fn edge_count(&self) -> usize {
        self.base.endpoints.len()
    }

    /// The copy's own cost, which is what matters: the base is shared by every
    /// graph descended from the same schema and counted once there.
    pub fn memory_usage(&self) -> usize {
        std::mem::size_of::<Self>() + self.class.capacity() * std::mem::size_of::<VertexId>()
    }

    pub fn base_memory_usage(&self) -> usize {
        let mut mem: usize = std::mem::size_of::<Base<L>>();

        mem += self.base.endpoints.capacity() * std::mem::size_of::<(VertexId, VertexId)>();
        mem += self.base.labels.capacity() * std::mem::size_of::<L>();
        mem += self.base.names.capacity() * std::mem::size_of::<String>();

        for name in &self.base.names {
            mem += name.capacity() * 2;
        }

        for incident in &self.base.incident {
            mem += incident.capacity() * std::mem::size_of::<EdgeId>();
        }

        mem
    }
}
